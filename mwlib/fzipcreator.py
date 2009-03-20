#! /usr/bin/env python
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.txt for additional licensing information.

"""
Rewrite of zipcreator.py which should be faster, 
since it relies totaly on the api.php and does not use the parser

TODO:
 * check if there are any other normalization issues
 * store expanded license information
 * use login to work with bot flag
 * testing
"""


import os
import pprint
import re
import tempfile
import threading
import zipfile
import urlparse
try:
    import json
except ImportError:
    import simplejson as json

from mwlib import mwapidb, utils, dummydb, namespace, metabook, jobsched
import mwlib.log

# ==============================================================================

log = mwlib.log.Log("fzipcreator")

pretty = pprint.PrettyPrinter(indent=1)

# ==============================================================================

def splitlist(lst, max=50):
    """Split a list in multiple parts"""

    parts = []
    while len(lst):
        parts.append(lst[:max])
        lst = lst[max:]
    return parts

def stripNS(title):
    """Strip namespace from title"""

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
        # FIXME: fetch transcluded stuff, images etc.

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
        image_names = set()
        template_names = set()
        articles = self.articles # title -> {content, revision}

        for job in jobs:
            d = dict(title=job['title'],
                     revision=job['revision'],
                     content=None,
                     contributors=[],
                     source=wikidb.getSource(job['title'], job['revision']),
                     url=wikidb.getURL(job['title'], job['revision'])
                     )
            self.articles[job["title"]] = d
 
        def _fetch(**kargs):
            res = wikidb.api_helper.query(ignore_errors=False, **kargs)

            self._trace(res)

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
                        del kargs[x]
                for d in continuations:
                    for k,v in d.items(): # dict of len(1)
                        kargs[str(k)] = v
                _fetch(**kargs)

        
        kwargs = dict(prop='revisions|templates|images',
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
                k['redirects'] = 1
                _fetch(**k)

        # fetch by revids
        if revids:
            for x in splitlist(revids, max=self.API_request_limit):
                k = kwargs.copy()
                k['revids'] = "|".join(x)
                _fetch(**k)

        return template_names, image_names
        

    def _fetchTemplates(self, wikidb, template_names, image_names):
        print_templates = set()
        if wikidb.print_template_pattern:
            for name in template_names:
                print_templates.add(wikidb.print_template_pattern.replace(u'$1', name))
        
        templates = self.templates # title -> {content, title}
        
        def _fetch(**kargs):
            res =  wikidb.api_helper.query(ignore_errors=False, **kargs)
            assert 'query-continue' not in res

            self._trace(res)

            for page in res["query"]["pages"].values():
                title = self.redirects.get(page["title"], page["title"])
                if "revisions" in page:
                    templates[title] = dict(content=page["revisions"][0]["*"],
                                            title=title)

                # Skip if template is in exclusion category:
                if wikidb.template_exclusion_category:
                    for c in page.get("categories", []):
                        if stripNS(c["title"]) == wikidb.template_exclusion_category:
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
        print_templates = set()
        if wikidb.print_template_pattern:
            for name in template_names:
                rname = name
                for k, v in self.redirects.items():
                    if v == name:
                        rname = k
                        break
                pname = wikidb.print_template_pattern.replace(u'$1', rname)
                if pname in templates:
                    print_templates.add(pname)
                    if name in templates:
                        templates[name]["content"] = templates[pname]["content"]
                    else:
                        templates[name] = templates[pname]
                
        # filter blacklisted templates
        if wikidb.template_blacklist:
            tbl = set(wikidb.template_blacklist) 
            for title, item in self.templates.items():
                if stripNS(title).lower() in tbl:
                    item["content"] = None
        
        # fetch images and templates of print_templates

        new_template_names = set()

        def _fetch_pt(**kargs):
            res =  wikidb.api_helper.query(ignore_errors=False, **kargs)
            assert 'query-continue' not in res
            self._trace(res)
            for page in res["query"]["pages"].values():
                for image in page.get("images", []):
                    image_names.add(image["title"])
                    print 'FOUND IMAGE', image['title']
                for template in page.get("templates", []):
                    t = template['title']
                    if t not in templates:
                        new_template_names.add(t)

        for ptitles in splitlist(list(print_templates), max=self.API_result_limit):
            _fetch_pt(
                titles="|".join(ptitles),
                redirects=1,
                prop='templates|images',
                tllimit=self.API_result_limit,
                imlimit=self.API_result_limit,
            )

        if new_template_names:
            self._fetchTemplates(new_template_names)

    def _fetchImages(self, wikidb, imagedb, image_names):
        images = self.images

        image_names = set([stripNS(n) for n in image_names])

        for name in image_names:
            images[name] = dict(title=name, 
                                url=None, 
                                thumburl=None, 
                                descriptionurl=None,
                                templates=[],
                                contributors=[],
                                api=None,
                                imagerepository=None,
                                content=None)

        # Get URLs:
        
        def _fetch_meta(**kargs):
            res = imagedb.api_helper.query(ignore_errors=False, **kargs)
            assert 'query-continue' not in res

            self._trace(res)

            for page in res["query"]["pages"].values():
                if not 'title' in page:
                    log.warn('No title in page element of query result. Skipping.')
                    continue
                title = self.redirects.get(page["title"], page["title"])
                title = stripNS(title)
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

        for ftitles in splitlist(list(image_names), max=self.API_request_limit):
            _fetch_meta(
                titles="|".join(['File:%s' % t for t in ftitles]),
                redirects=1,
                rvprop='content',
                prop='imageinfo|templates|revisions',
                iiprop="url",
                iiurlwidth=str(self.imagesize),
                iilimit=self.API_result_limit,
                tllimit=self.API_result_limit
                )


        # Get revision and templates for images from shared repository:

        def _fetch_shared_meta(api, **kargs):
            res = api.query(**kargs)
            self._trace(res)
            for page in res["query"]["pages"].values():
                title = self.redirects.get(page["title"], page["title"])
                title = stripNS(title)
                for template in page.get("templates", []):
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
            titles = [i["title"] for i in images.values()
                      if i and i["api"] == api and not i["templates"]]
            if not titles: # we should not need to fetch templates from the local wiki anymore
                continue
            for ftitles in splitlist(titles, max=self.API_request_limit):
                _fetch_shared_meta(api,
                    titles="|".join(['File:%s' % t for t in ftitles]),
                    redirects=1,
                    rvprop='content',
                    prop='templates|revisions',
                    tllimit=self.API_result_limit
                    )

        # Set contributors:

        get_contributors = imagedb.getContributorsFromInformationTemplate
        _dummydb = dummydb.DummyDB()  
        for title, image in images.items():
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
                zipname = u"images/%s" % image["title"].replace("'", '-')
                self.zf.write(filename, zipname.encode("utf-8"))
            finally:
                self.zf_lock.release()


        self.jobsched.add_job(image["title"], job)


    def scheduleContributors(self, title, object, wikidb):
        if not object:
            return 

        def job(job_id):
            contributors = wikidb.getAuthors(title, object.get("revision"), self.API_result_limit)
            if contributors:
                object["contributors"] = contributors

        self.jobsched.add_job(title, job)


    def writeContent(self):

        articles = {}
        templates = {}
        images = {}
        sources = {}

        allpages = self.articles.items() + self.templates.items()

        def istemplate(name, item):
            nsmap = None
            src = item.get('source')
            if src:
                try:
                    lang = src['language']
                    nsmap = namespace.namespace_maps['%s+en_mw' % lang]
                except KeyError:
                    pass
            ns, partial, full = namespace.splitname(name, nsmap=nsmap)
            return ns == namespace.NS_TEMPLATE

        # prepare articles & sources
        for name, item in allpages:
            if istemplate(name, item):
                continue
            articles[name] = {
                'content-type': 'text/x-wiki',
                'revision': item.get('revision'),
                'content': item['content'],
                'url': item.get('url'),
                'authors': item.get('contributors', []),
                }
            src = item.get('source')
            if src and 'url' in src:
                articles[name]['source-url'] = src['url']
                if src['url'] not in sources:
                    sources[src['url']] = src

        # prepare templates
        for name, item in self.templates.items():
            if not istemplate(name, item):
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
            images[name] = dict(url=item["thumburl"] or item['url'],
                                descriptionurl=item['descriptionurl'],
                                templates=item['templates'],
                                contributors=item['contributors'])
            
        data = dict(
            articles=articles,
            templates=templates,
            sources=sources,
            images=images,
            licenses=self.licenses
        )
        self.addObject('content.json', json.dumps(data))


    def join(self):
        # TODO: login as a bot, so we can request 5000 objects at once

        # split jobs by wikidb
        jobsbysite = dict()
        for job in self.article_jobs:
            jobsbysite.setdefault(job['wikidb'], []).append(job)

        # for each wiki
        for wikidb, jobs in jobsbysite.items():
            # get all article text next to template and image names 
            template_names, image_names = self._fetchArticles(wikidb, jobs)

            # get all templates or their print version
            self._fetchTemplates(wikidb, template_names, image_names)

            # get images
            imagedb = jobs[0]['imagedb']
            self._fetchImages(wikidb, imagedb, image_names)

            # get article contributors
            for a in self.articles.values():
                if not a:
                    continue
                self.scheduleContributors(a['title'], a, wikidb)

            # fetch image binaries
            for image in self.images.values():
                self.scheduleImageBinary(image)
            
            # get contributors for images w/o 
            apis = set(i["api"] for i in self.images.values() if i and i["api"])
            for api in apis:
                _wikidb = mwapidb.WikiDB(api_helper=api)
                for i in self.images.values():
                    if i and not i["contributors"] and i["api"] == api:
                        self.scheduleContributors('File:%s' % i['title'], i, _wikidb)
                        
        self.jobsched.join()
        self.writeContent()

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

        z.addLicenses(metabook.get_licenses(env.metabook))
        
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

        z.join()
        
        z.addObject('metabook.json', json.dumps(env.metabook))

        zf.close()

        checkzip(tmpzip) # DEBUG CODE

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
        

def checkzip(zip_filename):
    """debug code"""

    import writerbase, wiki

    env = wiki.makewiki(zip_filename)
    book = writerbase.build_book(env)
    print book
    print book.children
    for i, obj in enumerate(book.allchildren()):
        if obj.__class__.__name__ == "ImageLink":
            imgPath = env.images.getDiskPath(obj.target)
            print obj, imgPath
    print i, "children in total"
