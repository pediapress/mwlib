#! /usr/bin/env python

# Copyright (c) 2007-2009 PediaPress GmbH
# See README.txt for additional licensing information.

import os
import re
import tempfile
import threading
import zipfile
try:
    import json
except ImportError:
    import simplejson as json

from mwlib import expander, jobsched, metabook, mwapidb, parser, uparser, utils, dummydb
from mwlib.recorddb import RecordDB
import mwlib.log
import pprint
pretty =  pprint.PrettyPrinter(indent=4)


# ==============================================================================

log = mwlib.log.Log("fzipcreator")

# ==============================================================================

def splitlist(list, max=50):
    parts = []
    while len(list):
        parts.append(list[:max])
        list = list[max:]
    return parts

class ZipCreator(object):

    redirect_rex = re.compile(r'^#redirect:?\s*?\[\[(?P<redirect>.*?)\]\]', re.IGNORECASE)
   
    def __init__(self, zf,
        imagesize=None,
        num_threads=10,
        status=None,
        num_articles=None,
    ):
        """
        @param zf: ZipFile object
        @type zf: L{zipfile.ZipFile}
        
        @param imagesize: max. size of images
        @type imagesize: int
        
        @param num_threads: number of threads for parallel fetchgin
            (set to 0 to turn threading off)
        @type num_threads: int
        """

        
        self.zf = zf
        self.imagesize = imagesize
        self.status = status
        self.articles = {}
        self.templates = {}
#        self.sources = {}
        self.images = {}
        self.node_stats = {} 
        self.num_articles = num_articles
#       self.article_count = 0
#       self.image_infos = set()    
        self.zf_lock = threading.RLock()
        if num_threads > 0:
            self.jobsched = jobsched.JobScheduler(num_threads)
        else:
            self.jobsched = jobsched.DummyJobScheduler()
        self.article_jobs = []
        self.redirects = {} # to -> from 
        self.normalizations = {} # to -> from 
        self.tmpdir = tempfile.mkdtemp()


    def addObject(self, name, value):
        """Add a file with name and contents value to the ZIP file
        
        @param name: name for entry in ZIP file, will be UTF-8 encoded
        @type name: unicode
        
        @param value: content for ZIP file entry
        @type value: str
        """
        
        self.zf_lock.acquire()
        try:
            self.zf.writestr(name.encode('utf-8'), value)
        finally:
            self.zf_lock.release()
    
    def addArticle(self, title,
        revision=None,
        wikidb=None,
        imagedb=None,
    ):
        """Add article with given title and revision to ZIP file. This will add
        all referenced templates and images, too.
        
        @param title: article title
        @type title: unicode
        
        @param revision: article revision (optional)
        @type revision: int
        
        @param wikidb: WikiDB to use
        
        @param imagedb: ImageDB to use (optional)
        """
        
        self.article_jobs.append({
            'title': title,
            'revision': revision,
            'wikidb': wikidb,
            'imagedb': imagedb,
        })
    
    def parseArticle(self, title,
        revision=None,
        raw=None,
        wikidb=None,
        imagedb=None,
    ):
        """Parse article with given title, revision and raw wikitext, adding all
        referenced templates and images, but not adding the article itself.
        
        @param title: title of article
        @type title: unicode
        
        @param revision: revision of article (optional)
        @type revision: int
        
        @param raw: wikitext of article
        @type raw: unicode
        
        @param wikidb: WikiDB to use
        
        @param imagedb: ImageDB to use (optional)
        """
        print "parseArticle called", title


    def _trace(self, res):
        # not separated by wikis
        self._traceRedirects(res)
        self._traceNormalizations(res)

    def _traceRedirects(self, res):
        for d in res["query"].get("redirects", []):
            self.redirects[d["to"]] = d["from"]

    def _traceNormalizations(self, res):
        for d in res["query"].get("normalized", []):
            self.normalizations[d["to"]] = d["from"]
        

    def _fetchArticles(self, wikidb, jobs):
        # NO SUPPORT FOR REVISIONS
        # NO ERROR HANDLING
        # CONTENT NOT STORED
        image_names = set()
        template_names = set()
        articles = self.articles # title -> {content, title}

        def _fetch(**kargs):
            res =  wikidb.api_helper.query(**kargs)
            assert not "warnings" in res
            self._trace(res)
#            pretty.pprint(res)

            for page in res["query"]["pages"].values():
                for image in page.get("images",[]):
                    image_names.add(image["title"])
                for template in page.get("templates",[]):
                    template_names.add(template["title"])
                title = self.redirects.get(page["title"], page["title"])
                if "revisions" in page:
                    articles[title] = dict(content=page["revisions"][0]["*"],
                                           title=title)
                else:
                    articles[title] = None

            continuations = res.get("query-continue", {}).values()
            if continuations:
                for x in ("imcontinue", "tlcontinue"):
                    if x in kargs:
                        del x
                for d in continuations:
                    for k,v in d.items(): # dict of len(1)
                        kargs[str(k)] = v
                _fetch(**kargs)

        titles = list(job["title"] for job in jobs)
        for ftitles in splitlist(titles, max=50):
            _fetch(
                titles="|".join(ftitles),
                redirects=1,
                prop='revisions|templates|images',
                rvprop='content',
                imlimit=500,
                tllimit=500,
                )
       
        # do something with the articles
        print len(template_names), "template names"
        print len(image_names), "image names"
        print len(articles), "articles"
        return template_names, image_names
        

    def _fetchTemplates(self, wikidb, template_names):
        # NO ERROR HANDLING
        # CONTENT NOT STORED
        print_templates = set()
        if wikidb.print_template_pattern:
            for name in template_names:
                print_templates.add(
                    wikidb.print_template_pattern.replace(u'$1', name))
        
        templates = self.templates # title -> {title, content}
        
        def _fetch(**kargs):
            res =  wikidb.api_helper.query(**kargs)
#            pretty.pprint(res)
            assert not "query-continue" in res
            assert not "warnings" in res
            self._trace(res)
            for page in res["query"]["pages"].values():
                title = self.redirects.get(page["title"], page["title"])
                if "revisions" in page:
                    templates[title] = dict(content=page["revisions"][0]["*"],
                                          title=title)
                # SKIP IF IN EXCLUDE CAT
                for c in page.get("categories", []):
                    cname = c["title"].split(":",1)[1] # NS stripped
                    if cname == wikidb.template_exclusion_category:
                        del templates[title]

        titles = list(template_names.union(print_templates))
        for ftitles in splitlist(titles, max=50):
            _fetch(
                titles="|".join(ftitles),
                redirects=1,
                prop='revisions|categories',
                rvprop='content',
                cllimit=500,
            )

        # substitute print templates
        for name in template_names:
            pname = wikidb.print_template_pattern.replace(u'$1', name)
            if pname in templates:
                templates[name]["content"] = templates[pname]["content"]
                del templates[pname]

        # do something with the articles
        print len(templates), "templates of", len(template_names)
        print len(template_names) - len(templates), "templates excluded in print"


    def _fetchImages(self, wikidb, imagedb, image_names):
        # NO ERROR HANDLING
        # CONTENT NOT STORED
        images = self.images
        for name in image_names:
            images[name] = dict(title=name, 
                                url=None, 
                                thumburl=None, 
                                descriptionurl=None,
                                templates=[],
                                contributors=[],
                                api=None,
                                imagerepository=None,
                                content = None)



        # get URL and description  -----------------------------------------
        
        def _fetch_meta(**kargs):
            res =  imagedb.api_helper.query(**kargs)
            assert not "query-continue" in res
            assert not "warnings" in res
            self._trace(res)
            for page in res["query"]["pages"].values():
                title = self.redirects.get(page["title"], page["title"])
#                pretty.pprint(page)
                images[title]["imagerepository"] = page.get("imagerepository")
                if "imageinfo" in page and page["imageinfo"]:
                    ii = page["imageinfo"][0]
                    images[title]["descriptionurl"] = ii["descriptionurl"]
                    images[title]["thumburl"] = ii.get("thumburl")
                    url = images[title]["url"] = ii.get("url")
                    if url and url.startswith('/'):
                        images[title]["url"]= urlparse.urljoin(imagedb.api_helper.base_url, url)
                    images[title]["api"] = mwapidb.get_api_helper(ii["descriptionurl"] or url)
                for template in page.get("templates",[]):
                    images[title]["templates"].append(template["title"])
                if "revisions" in page:
                    images[title]["content"] = page["revisions"][0]["*"]
            """
            for d in res.get("query-continue", {}).values():
                for k,v in d.items(): # dict of len(1)
                    kargs[str(k)] = v
                _fetch(**kargs)
            """

        for ftitles in splitlist(list(image_names), max=50):
            _fetch_meta(
                titles="|".join(ftitles),
                redirects=1,
                rvprop='content',
                prop='imageinfo|templates|revisions',
                iiprop="url",
                iiurlwidth=str(self.imagesize),
                iilimit=500,
                tllimit=500
                )


        # get templates  -----------------------------------------

        def _fetch_shared_meta(api, **kargs):
            res =  api.query(**kargs)
            assert not "warnings" in res
            self._trace(res)
            for page in res["query"]["pages"].values():
#                pretty.pprint(page)
                title = self.redirects.get(page["title"], page["title"])
                for template in page.get("templates",[]):
                    images[title]["templates"].append(template["title"])
                images[title]["content"] = page["revisions"][0]["*"]
            for d in res.get("query-continue", {}).values():
                for k,v in d.items(): # dict of len(1)
                    kargs[str(k)] = v
                _fetch_shared_meta(api, **kargs)


        apis = set(i["api"] for i in images.values())
        for api in apis:
            if not api:
                continue
            titles = [i["title"] for i in images.values() \
                          if i["api"] == api and not i["templates"]]
            if not titles: # we should not need to fetch templates from the local wiki anymore
                continue
            for ftitles in splitlist(titles, max=50):
                _fetch_shared_meta(api,
                    titles="|".join(ftitles),
                    redirects=1,
                    rvprop='content',
                    prop='templates|revisions',
                    tllimit=500
                    )

        # set contributors
        get_contributors = imagedb.getContributorsFromInformationTemplate
        _dummydb = dummydb.DummyDB()  
        for title, image in images.items():
            # parse contributors from "Template:Information" if available
            if image["content"] and "Template:Information" in image["templates"]:
                contributors = get_contributors(image["content"], title, _dummydb)
                if contributors:
                    image["contributors"] = contributors

        print len(images), "images"
        print len(list(i for i in images.values() if i["contributors"])), "images with contributors"
        # --- start threaded jobs to get the binaries



    def scheduleImageBinary(self, image):
        
        def job(job_id):
            url = image["thumburl"] or image["url"]
            assert url
            ext = url.rsplit('.')[-1]
            size = None # FIXME
            if size is not None:
                ext = '%dpx.%s' % (size, ext)
            else:
                ext = '.%s' % ext
            filename = os.path.join(self.tmpdir, utils.fsescape(image["title"] + ext))    
            if not utils.fetch_url(url, ignore_errors=True, output_filename=filename):
                log.warn('Could not get image %r' % name)
                return
            self.zf_lock.acquire()
            try:
                zipname = u"images/%s" % image["title"].replace("'", '-')
                self.zf.write(filename, zipname.encode("utf-8"))
            finally:
                self.zf_lock.release()


        self.jobsched.add_job(image["title"], job)


    def scheduleContributors(self, object, wikidb):
        
        def job(job_id):
            contributors = wikidb.getAuthors(object["title"]) # FIXME revision
            if contributors:
                object["contributors"] = contributors

        self.jobsched.add_job(object["title"], job)


    def join(self):
        # login as a bot, so we can request 5000 objects at once


        # split jobs by wikidb
        jobsbysite = dict()
        for job in self.article_jobs:
            jobsbysite.setdefault(job['wikidb'], []).append(job)

        # for each wiki
        for wikidb, jobs in jobsbysite.items():
            # get all article text next to template and image names 
            template_names, image_names = self._fetchArticles(wikidb, jobs)

            # get all blacklisted templates, all excluded templates
            tbl = set(wikidb.template_blacklist) # NS is stripped
            template_names = set(t for t in template_names if not t.split(":",1)[1] in tbl)

            # get all templates or their print version
            self._fetchTemplates(wikidb, template_names)

            # get images
            imagedb = jobs[0]['imagedb']
            self._fetchImages(wikidb, imagedb, image_names)

            # get article contributors
            for a in self.articles.values():
                self.scheduleContributors(a, wikidb)

            # fetch image binaries
            for image in self.images.values():
                self.scheduleImageBinary(image)
            
            # get contributors for images w/o 
            apis = set(i["api"] for i in self.images.values())
            for api in apis:
                if not api:
                    continue
                _wikidb = mwapidb.WikiDB(api_helper=api)
                for i in self.images.values():
                    if not i["contributors"] and i["api"] == api:
                        self.scheduleContributors(i, _wikidb)
                        
        self.jobsched.join()
        for i in self.images.values():
            if not i["api"]:
                print i



def make_zip_file(output, env,
    status=None,
    num_threads=10,
    imagesize=800,
):
    if output is None:
        fd, output = tempfile.mkstemp(suffix='.zip')
        os.close(fd)
    
    fd, tmpzip = tempfile.mkstemp(suffix='.zip', dir=os.path.dirname(output))
    os.close(fd)
    zf = zipfile.ZipFile(tmpzip, 'w')
    
    try:
        articles = metabook.get_item_list(env.metabook, filter_type='article')
        
        z = ZipCreator(zf,
            imagesize=imagesize,
            num_threads=num_threads,
            status=status,
            num_articles=len(articles),
        )
        
        for item in articles:
            d = mwapidb.parse_article_url(item['title'].encode('utf-8'))
            if d is not None:
                item['title'] = d['title']
                item['revision'] = d['revision']
                wikidb = mwapidb.WikiDB(api_helper=d['api_helper'])
                imagedb = mwapidb.ImageDB(api_helper=d['api_helper'])
            else:
                wikidb = env.wiki
                imagedb = env.images
            z.addArticle(item['title'],
                revision=item.get('revision', None),
                wikidb=wikidb,
                imagedb=imagedb,
            )

        for license in env.get_licenses():
            z.parseArticle(
                title=license['title'],
                raw=license['wikitext'],
                wikidb=env.wiki,
                imagedb=env.images,
            )
        
        z.join()
        
        # using check() is a bit rigorous: sometimes articles just cannot be
        # fetched -- PDFs should be generated nevertheless
        #z.check(articles)

        z.addObject('metabook.json', json.dumps(env.metabook))

        # add stats for later analysis
        z.node_stats["Chapter"] = len(metabook.get_item_list(env.metabook, filter_type='chapter'))
        z.addObject('node_stats.json', json.dumps(z.node_stats)) 

        zf.close()
        if os.path.exists(output): # Windows...
            os.unlink(output)
        os.rename(tmpzip, output)
    
        if env.images and hasattr(env.images, 'clear'):
            env.images.clear()
    
        if status is not None:
            status(progress=100)
        return output
    finally:
        if os.path.exists(tmpzip):
            utils.safe_unlink(tmpzip)
