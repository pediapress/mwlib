#! /usr/bin/env python
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.txt for additional licensing information.

"""
Rewrite of zipcreator.py which should be faster, 
since it relies totaly on the api.php and does not use the parser

TODO:
 * check if redirects work with revisions
 * check if there are any other normalization issues
 * store expanded license information
 * use login to work with bot flag
 * testing
"""


import os
import re
import tempfile
import threading
import zipfile
import urlparse
try:
    import json
except ImportError:
    import simplejson as json

from mwlib import jobsched, metabook 
from mwlib import mwapidb, utils, dummydb, namespace
import mwlib.log
import pprint
pretty =  pprint.PrettyPrinter(indent=1)


# ==============================================================================

log = mwlib.log.Log("fzipcreator")

# ==============================================================================

def splitlist(list, max=50):
    "split a list in multiple parts"
    parts = []
    while len(list):
        parts.append(list[:max])
        list = list[max:]
    return parts

def stripNS(title):
    assert ":" in title
    return title.split(":",1)[1]

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

        self.API_result_limit = 500 # 5000 for bots
        self.API_request_limit = 50 # at max 50 titles at once
        self.zf = zf
        self.imagesize = imagesize
        self.status = status
        self.articles = {}
        self.templates = {}
        self.images = {}
        self.node_stats = {} 
        self.num_articles = num_articles
        self.zf_lock = threading.RLock()
        if num_threads > 0:
            self.jobsched = jobsched.JobScheduler(num_threads)
        else:
            self.jobsched = jobsched.DummyJobScheduler()
        self.article_jobs = []
        self.redirects = {} # to -> from 
        self.normalizations = {} # to -> from 
        self.tmpdir = tempfile.mkdtemp()
        self.licenses = []

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
    
    def addLicenses(self, licenses):
        """
        @param licenses: [dict(title="title", wikitext="raw expanded")]
        @type licenses: list
        """
        self.licenses = licenses

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
        # NO ERROR HANDLING
        image_names = set()
        template_names = set()
        articles = self.articles # title -> {content, title}

        for job in jobs:
            d = dict(title=job['title'],
                     revision=job['revision'],
                     content=None,
                     contributors=[],
                     source = wikidb.getSource(job['title'], job['revision']),
                     url = wikidb.getURL(job['title'], job['revision'])
                     )
            self.articles[job["title"]] = d
 
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
                    articles[title]['content'] = page["revisions"][0]["*"]
                    articles[title]['revision'] = unicode(page["revisions"][0]["revid"])
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

        
        kwargs = dict(redirects=1,
                      prop='revisions|templates|images',
                      rvprop='ids|content',
                      imlimit=self.API_result_limit,
                      tllimit=self.API_result_limit)

        # prepare both, revids will be added
        titles = list(job['title'] for job in jobs if not job['revision'])
        revids = list(job['revision'] for job in jobs if job['revision'])

        # fetch by title
        if titles:
            for x in splitlist(titles, max=self.API_request_limit):
                k = kwargs.copy()
                k['titles'] = "|".join(x)
                _fetch(**k)

        # fetch by revids
        if revids:
            for x in splitlist(revids, max=self.API_request_limit):
                k = kwargs.copy()
                k['revids'] = "|".join(x)
                del k["redirects"] # FIXME? redirects won't be resolved ...
                _fetch(**k)

        return template_names, image_names
        

    def _fetchTemplates(self, wikidb, template_names):
        # NO ERROR HANDLING
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
                    cname = stripNS(c["title"]) # NS stripped
                    if cname == wikidb.template_exclusion_category:
                        templates[title]['content'] = None

        titles = list(template_names.union(print_templates))
        for ftitles in splitlist(titles, max=self.API_request_limit):
            _fetch(
                titles="|".join(ftitles),
                redirects=1,
                prop='revisions|categories',
                rvprop='content',
                cllimit=self.API_result_limit,
            )

        # substitute print templates
        for name in template_names:
            pname = wikidb.print_template_pattern.replace(u'$1', name)
            if pname in templates:
                templates[name]["content"] = templates[pname]["content"]
                del templates[pname]
                
        # filter  blacklisted templates
        tbl = set(wikidb.template_blacklist) 
        for title, item in self.templates.items():
            if stripNS(title).lower() in tbl:
                item["content"] = None


    def _fetchImages(self, wikidb, imagedb, image_names):
        # NO ERROR HANDLING
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
                else:
                    images[title] = None
                    continue 
                for template in page.get("templates",[]):
                    images[title]["templates"].append(stripNS(template["title"]))
                if "revisions" in page:
                    images[title]["content"] = page["revisions"][0]["*"]
            """
            for d in res.get("query-continue", {}).values():
                for k,v in d.items(): # dict of len(1)
                    kargs[str(k)] = v
                _fetch(**kargs)
            """

        for ftitles in splitlist(list(image_names), max=self.API_request_limit):
            _fetch_meta(
                titles="|".join(ftitles),
                redirects=1,
                rvprop='content',
                prop='imageinfo|templates|revisions',
                iiprop="url",
                iiurlwidth=str(self.imagesize),
                iilimit=self.API_result_limit,
                tllimit=self.API_result_limit
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
                    images[title]["templates"].append(stripNS(template["title"]))
                images[title]["content"] = page["revisions"][0]["*"]
            for d in res.get("query-continue", {}).values():
                for k,v in d.items(): # dict of len(1)
                    kargs[str(k)] = v
                _fetch_shared_meta(api, **kargs)


        apis = set(i["api"] for i in images.values() if i)
        for api in apis:
            if not api:
                continue
            titles = [i["title"] for i in images.values() \
                          if i and i["api"] == api and not i["templates"]]
            if not titles: # we should not need to fetch templates from the local wiki anymore
                continue
            for ftitles in splitlist(titles, max=self.API_request_limit):
                _fetch_shared_meta(api,
                    titles="|".join(ftitles),
                    redirects=1,
                    rvprop='content',
                    prop='templates|revisions',
                    tllimit=self.API_result_limit
                    )

        # set contributors
        get_contributors = imagedb.getContributorsFromInformationTemplate
        _dummydb = dummydb.DummyDB()  
        for title, image in images.items():
            # parse contributors from "Template:Information" if available
            if image and image["content"] and "Information" in image["templates"]:
                contributors = get_contributors(image["content"], title, _dummydb)
                if contributors:
                    image["contributors"] = contributors


    def scheduleImageBinary(self, image):
        if not image:
            return

        def job(job_id):
            url = image["thumburl"] or image["url"]
            assert url
            ext = url.rsplit('.')[-1]
            size = self.imagesize
            if size is not None:
                ext = '%dpx.%s' % (size, ext)
            else:
                ext = '.%s' % ext
            filename = os.path.join(self.tmpdir, utils.fsescape(image["title"] + ext))    
            if not utils.fetch_url(url, ignore_errors=True, output_filename=filename):
                log.warn('Could not get image %r' % image["name"])
                return
            self.zf_lock.acquire()
            try:
                zipname = u"images/%s" % stripNS(image["title"]).replace("'", '-')
                self.zf.write(filename, zipname.encode("utf-8"))
            finally:
                self.zf_lock.release()


        self.jobsched.add_job(image["title"], job)


    def scheduleContributors(self, object, wikidb):
        if not object:
            return 

        def job(job_id):
            contributors = wikidb.getAuthors(object["title"], object.get("revision"), self.API_result_limit)
            if contributors:
                object["contributors"] = contributors

        self.jobsched.add_job(object["title"], job)


    def writeContent(self):

        articles = {}
        templates = {}
        images = {}
        sources = {}

        def istemplate(name):
            ns, partial, full = namespace.splitname(name)
            return ns == namespace.NS_TEMPLATE


        # prepare articles & sources
        allpages = self.articles.items() + self.templates.items()
        
        for name, item in allpages:
            if istemplate(name):
                continue
            articles[name] = {
                'content-type': 'text/x-wiki',
                'revision': item.get('revision'),
                'content': item['content'],
                'url': item.get('url'),
                'authors': item.get('contributors',[]),
                }
            src  = item.get('source')
            if src and 'url' in src:
                articles[name]['source-url'] = src['url']
                if src['url'] not in sources:
                    sources[src['url']] = src

        # prepare templates
        for name, item in self.templates.items():
            if not istemplate(name):
                continue
            ns, partial, full = namespace.splitname(name)
            if ns==namespace.NS_TEMPLATE:
                templates[partial] = {
                    'content-type': 'text/x-wiki',
                    'content': item['content'],
                    }

        # prepare images
        for name, item in self.images.items():
            if not item:
                continue
            images[stripNS(name)] = dict(url = item["thumburl"] or item['url'],
                                         descriptionurl = item['descriptionurl'],
                                         templates =  item['templates'],
                                         contributors = item['contributors'])
            
        data = dict(
            articles=articles,
            templates=templates,
            sources=sources,
            images=images,
            licenses=self.licenses
        )
        self.addObject('content.json', json.dumps(data))
#        del data["sources"]
#        pretty.pprint(data)


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

            # get all templates or their print version
            def _getTemplates(jobname):
                self._fetchTemplates(wikidb, template_names)
            
            # get images
            def _getImageData(jobname):
                imagedb = jobs[0]['imagedb']
                self._fetchImages(wikidb, imagedb, image_names)

            # fetch image data and templates in parallel
            self.jobsched.add_job("_getTemplates", _getTemplates)
            self.jobsched.add_job("_getImageData", _getImageData)
            self.jobsched.join()

            # get article contributors
            for a in self.articles.values():
                self.scheduleContributors(a, wikidb)

            # fetch image binaries
            for image in self.images.values():
                self.scheduleImageBinary(image)
            
            # get contributors for images w/o 
            apis = set(i["api"] for i in self.images.values() if i and i["api"])
            for api in apis:
                _wikidb = mwapidb.WikiDB(api_helper=api)
                for i in self.images.values():
                    if i and not i["contributors"] and i["api"] == api:
                        self.scheduleContributors(i, _wikidb)
                        
        self.jobsched.join()
        self.writeContent()



    def check(self):
        for item in self.articles.values():
            try:
                article = self.articles[item['title']]
            except KeyError:
                raise RuntimeError('Could not fetch article %r' % item['title'])
            if not article.get('url'):
                raise RuntimeError('Have no URL for article %r' % item['title'])
            if not article.get('source-url'):
                raise RuntimeError('Have no source URL for article %r' % item['title'])
            if not article.get('content'):
                raise RuntimeError('Have empty content for article %r' % item['title'])
            if not article['source-url'] in self.sources:
                raise RuntimeError('Unknown source URL %r for article %r' % (
                    article['source-url'], item['title']),
                )

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

        z.addLicenses(env.get_licenses())
        
        z.join()
        
        # using check() is a bit rigorous: sometimes articles just cannot be
        # fetched -- PDFs should be generated nevertheless
        #z.check(articles)
        z.addObject('metabook.json', json.dumps(env.metabook))
#        pretty.pprint(env.metabook)

        zf.close()
        if os.path.exists(output): # Windows...
            os.unlink(output)
        os.rename(tmpzip, output)
    
        if env.images and hasattr(env.images, 'clear'):
            env.images.clear()
    
        if status is not None:
            status(progress=100)
#        checkzip(output)
        return output
    finally:
        if os.path.exists(tmpzip):
            utils.safe_unlink(tmpzip)
        

def checkzip(zip_filename):
    "debug code"
    import writerbase, wiki, zipwiki
    env = wiki.makewiki(zip_filename)
    env.wiki = zipwiki.Wiki(zip_filename)
    env.images = zipwiki.ImageDB(zip_filename)
    book = writerbase.build_book(env)
    print book
    print book.children
    for i, obj in enumerate(book.allchildren()):
        if obj.__class__.__name__ == "ImageLink":
            imgPath = env.images.getDiskPath(obj.target)
            print obj, imgPath
    print i, "children in total"
