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
import tempfile
import threading
import zipfile
import urlparse
try:
    import json
except ImportError:
    import simplejson as json

from mwlib import mwapidb, utils, dummydb, namespace, jobsched
from mwlib import metabook as metabook_mod
import mwlib.log

# ==============================================================================

log = mwlib.log.Log("fzipcreator")

# ==============================================================================

def splitlist(lst, max=50):
    """Split a list in multiple parts"""

    parts = []
    while len(lst):
        parts.append(lst[:max])
        lst = lst[max:]
    return parts

def splitname(name, lang):
    """Return namesapce number, partial title and full title"""

    nsmap = None
    if lang:
        try:
            nsmap = namespace.namespace_maps['%s+en_mw' % lang]
        except KeyError:
            raise # DEBUG
            pass
    return namespace.splitname(name, nsmap=nsmap)

# ==============================================================================

class WikiFetcher(object):
    api_result_limit = 500 # 5000 for bots
    api_request_limit = 50 # at most 50 titles at once

    def __init__(self, zipcreator, wikidb, imagedb):
        self.zipcreator = zipcreator
        self.jobsched = zipcreator.jobsched
        self.wikidb = wikidb
        self.imagedb = imagedb
        self.imagesize = zipcreator.imagesize
        self.articles = {}
        self.templates = {}
        self.images = {}
        self.article_jobs = []
        self.redirects = {} # to -> from 
        self.normalizations = {} # to -> from 
        self.tmpdir = tempfile.mkdtemp()
        self.licenses = []
        self.source = self.wikidb.getSource(None)
        self.lang = self.source['language']

    def addArticle(self, title, revision=None):
        """Fetch article with given title and revision. This will fetch
        all referenced templates and images, too.
        
        @param title: article title
        @type title: unicode
        
        @param revision: article revision (optional)
        @type revision: int
        """
        
        self.article_jobs.append({
            'title': title,
            'revision': revision,
        })
    
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

    def strip_ns(self, removens, title):
        """Strip namespace from title"""

        ns, partial, full = splitname(title, self.lang)
        if ns == removens:
            return partial.replace('_', ' ')
        return title

    def istemplate(self, title):
        return splitname(title, self.lang)[0] == namespace.NS_TEMPLATE
        
    def _fetchArticles(self):
        image_names = set()
        template_names = set()
        articles = self.articles # title -> {content, revision}

        for job in self.article_jobs:
            d = dict(title=job['title'],
                     revision=job['revision'],
                     content=None,
                     contributors=[],
                     source=self.source,
                     url=self.wikidb.getURL(job['title'], job['revision'])
                     )
            self.articles[job["title"]] = d
 
        def _fetch(**kargs):
            res = self.wikidb.api_helper.query(ignore_errors=False, **kargs)

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
                      imlimit=self.api_result_limit,
                      tllimit=self.api_result_limit)

        # prepare both, revids will be added
        titles = list(job['title'] for job in self.article_jobs if not job['revision'])
        revids = list(job['revision'] for job in self.article_jobs if job['revision'])

        # fetch by title
        if titles:
            for x in splitlist(titles, max=self.api_request_limit):
                k = kwargs.copy()
                k['titles'] = "|".join(x)
                k['redirects'] = 1
                _fetch(**k)

        # fetch by revids
        if revids:
            for x in splitlist(revids, max=self.api_request_limit):
                k = kwargs.copy()
                k['revids'] = "|".join(x)
                _fetch(**k)

        return template_names, image_names

    def _fetchTemplates(self, template_names, image_names):
        print_templates = set()
        if self.wikidb.print_template_pattern:
            for name in template_names:
                print_templates.add(self.wikidb.print_template_pattern.replace(u'$1', name))
        
        templates = self.templates # title -> {content, title}
        
        def _fetch(**kargs):
            res = self.wikidb.api_helper.query(ignore_errors=False, **kargs)
            assert 'query-continue' not in res

            self._trace(res)

            for page in res["query"]["pages"].values():
                title = self.redirects.get(page["title"], page["title"])
                if "revisions" in page:
                    templates[title] = dict(content=page["revisions"][0]["*"],
                                            title=title)

                # Skip if template is in exclusion category:
                if self.wikidb.template_exclusion_category:
                    for c in page.get("categories", []):
                        if self.strip_ns(namespace.NS_CATEGORY, c["title"]) == self.wikidb.template_exclusion_category:
                            templates[title]['content'] = None

        titles = list(template_names.union(print_templates))
        for ftitles in splitlist(titles, max=self.api_request_limit):
            _fetch(
                titles="|".join(ftitles),
                redirects=1,
                prop='revisions|categories',
                rvprop='content',
                cllimit=self.api_result_limit,
            )

        # substitute print templates
        print_templates = set()
        if self.wikidb.print_template_pattern:
            for name in template_names:
                rname = name
                for k, v in self.redirects.items():
                    if v == name:
                        rname = k
                        break
                pname = self.wikidb.print_template_pattern.replace(u'$1', rname)
                if pname in templates:
                    print_templates.add(pname)
                    templates[name] = templates[pname]
                
        # filter blacklisted templates
        if self.wikidb.template_blacklist:
            tbl = set(self.wikidb.template_blacklist) 
            for title, item in self.templates.items():
                if self.strip_ns(namespace.NS_TEMPlATE, title).lower() in tbl:
                    item["content"] = None
        
        # fetch images and templates of print_templates

        new_template_names = set()

        def _fetch_pt(**kargs):
            res =  self.wikidb.api_helper.query(ignore_errors=False, **kargs)
            assert 'query-continue' not in res
            self._trace(res)
            for page in res["query"]["pages"].values():
                for image in page.get("images", []):
                    image_names.add(image["title"])
                for template in page.get("templates", []):
                    t = template['title']
                    if t not in templates:
                        new_template_names.add(t)

        for ptitles in splitlist(list(print_templates), max=self.api_result_limit):
            _fetch_pt(
                titles="|".join(ptitles),
                redirects=1,
                prop='templates|images',
                tllimit=self.api_result_limit,
                imlimit=self.api_result_limit,
            )

        if new_template_names:
            self._fetchTemplates(new_template_names)

    def _fetchImages(self, image_names):
        images = self.images

        image_names = set([self.strip_ns(namespace.NS_IMAGE, n) for n in image_names])

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
            res = self.imagedb.api_helper.query(ignore_errors=False, **kargs)
            assert 'query-continue' not in res

            self._trace(res)

            for page in res["query"]["pages"].values():
                if not 'title' in page:
                    log.warn('No title in page element of query result. Skipping.')
                    continue
                title = self.redirects.get(page["title"], page["title"])
                title = self.strip_ns(namespace.NS_IMAGE, title)
                images[title]["imagerepository"] = page.get("imagerepository")
                if "imageinfo" in page and page["imageinfo"]:
                    ii = page["imageinfo"][0]
                    images[title]["descriptionurl"] = ii["descriptionurl"]
                    images[title]["thumburl"] = ii.get("thumburl")
                    url = images[title]["url"] = ii.get("url")
                    if url and url.startswith('/'):
                        images[title]["url"]= urlparse.urljoin(self.imagedb.api_helper.base_url, url)
                    images[title]["api"] = mwapidb.get_api_helper(ii["descriptionurl"] or url)
                else:
                    images[title] = None
                    continue 
                for template in page.get("templates",[]):
                    images[title]["templates"].append(self.strip_ns(namespace.NS_TEMPLATE, template["title"]))
                if "revisions" in page:
                    images[title]["content"] = page["revisions"][0]["*"]

        for ftitles in splitlist(list(image_names), max=self.api_request_limit):
            _fetch_meta(
                titles="|".join(['File:%s' % t for t in ftitles]),
                redirects=1,
                rvprop='content',
                prop='imageinfo|templates|revisions',
                iiprop="url",
                iiurlwidth=str(self.imagesize),
                iilimit=self.api_result_limit,
                tllimit=self.api_result_limit
                )


        # Get revision and templates for images from shared repository:

        def _fetch_shared_meta(api, **kargs):
            res = api.query(**kargs)
            self._trace(res)
            for page in res["query"]["pages"].values():
                title = self.redirects.get(page["title"], page["title"])
                title = self.strip_ns(namespace.NS_IMAGE, title)
                for template in page.get("templates", []):
                    images[title]["templates"].append(self.strip_ns(namespace.NS_TEMPLATE, template['title']))
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
            for ftitles in splitlist(titles, max=self.api_request_limit):
                _fetch_shared_meta(api,
                    titles="|".join(['File:%s' % t for t in ftitles]),
                    redirects=1,
                    rvprop='content',
                    prop='templates|revisions',
                    tllimit=self.api_result_limit
                    )

        # Set contributors:

        get_contributors = self.imagedb.getContributorsFromInformationTemplate
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
            zipname = u"images/%s" % image["title"].replace("'", '-')
            self.zipcreator.addFile(filename, zipname.encode("utf-8"))

        self.jobsched.add_job(image["title"], job)

    def _fetchContributors(self):
        for a in self.articles.values():
            if not a:
                continue
            self.scheduleContributors(a['title'], a)

    def scheduleContributors(self, title, object, wikidb=None):
        if wikidb is None:
            wikidb = self.wikidb
        def job(job_id):
            contributors = wikidb.getAuthors(title, object.get("revision"), self.api_result_limit)
            if contributors:
                object["contributors"] = contributors
        self.jobsched.add_job(title, job)

    def _fetchImageBinaries(self):
        for image in self.images.values():
            self.scheduleImageBinary(image)

        # get contributors for images w/o 
        apis = set(i["api"] for i in self.images.values() if i and i["api"])
        for api in apis:
            _wikidb = mwapidb.WikiDB(api_helper=api)
            for i in self.images.values():
                if i and not i["contributors"] and i["api"] == api:
                    self.scheduleContributors('File:%s' % i['title'], i, _wikidb)
                        


# ==============================================================================


class ZipCreator(object):
    def __init__(self, zf, metabook,
        num_threads=10,
        imagesize=None,
    ):
        """
        @param zf: ZipFile object
        @type zf: L{zipfile.ZipFile}
        
        @param num_threads: number of threads for parallel fetchgin
            (set to 0 to turn threading off)
        @type num_threads: int
        """

        self.zf = zf
        self.metabook = metabook
        self.addLicenses(metabook_mod.get_licenses(self.metabook))
        
        self.zf_lock = threading.RLock()

        self.imagesize = imagesize

        if num_threads > 0:
            self.jobsched = jobsched.JobScheduler(num_threads)
        else:
            self.jobsched = jobsched.DummyJobScheduler()
        
        self.fetchers = {}

    def scheduleArticle(self, title, revision, wikidb, imagedb):
        try:
            fetcher = self.fetchers[wikidb]
        except KeyError:
            fetcher = WikiFetcher(self, wikidb, imagedb)
            self.fetchers[wikidb] = fetcher
        fetcher.addArticle(title, revision)

    def addFile(self, name, filename):
        """Add a file with name and contents from file filename to the ZIP file
        
        @param name: name for entry in ZIP file, will be UTF-8 encoded
        @type name: unicode
        
        @param filename: filename to read from
        @type filanem: basestring
        """
        
        self.zf_lock.acquire()
        try:
            self.zf.write(name.encode('utf-8'), filename)
        finally:
            self.zf_lock.release()
    
    def addString(self, name, value):
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

    def addLicenses(self, licenses):
        """
        @param licenses: [dict(title="title", wikitext="raw expanded")]
        @type licenses: list
        """

        self.licenses = licenses
        # FIXME: fetch transcluded stuff, images etc.
    
    def writeContent(self):
        articles = {}
        templates = {}
        images = {}
        sources = {}

        for fetcher in self.fetchers.values():
            allpages = fetcher.articles.items() + fetcher.templates.items()

            # prepare articles & sources
            for name, item in allpages:
                if item is None:
                    continue
                if fetcher.istemplate(name):
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
            for name, item in allpages:
                if item is None:
                    continue
                if not fetcher.istemplate(name):
                    continue
                templates[fetcher.strip_ns(namespace.NS_TEMPLATE, name)] = {
                    'content-type': 'text/x-wiki',
                    'content': item['content'],
                    }

            # prepare images
            for name, item in fetcher.images.items():
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
        self.addString('content.json', json.dumps(data))
        self.addString('metabook.json', json.dumps(self.metabook))
        self.zf.close()

    def run(self):
        for fetcher in self.fetchers.values():
            # get all article text next to template and image names 
            template_names, image_names = fetcher._fetchArticles()

            # get all templates or their print version
            fetcher._fetchTemplates(template_names, image_names)

            # get images
            fetcher._fetchImages(image_names)

            # get article contributors
            fetcher._fetchContributors()

            # fetch image binaries
            fetcher._fetchImageBinaries()
            
        self.jobsched.join()

        self.writeContent()


# ==============================================================================

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
        articles = metabook_mod.get_item_list(env.metabook, filter_type='article')
        
        z = ZipCreator(zf,
            metabook=env.metabook,
            imagesize=imagesize,
            num_threads=num_threads,
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
            z.scheduleArticle(item['title'],
                revision=item.get('revision', None),
                wikidb=wikidb,
                imagedb=imagedb,
            )

        z.run()
        
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
        
# ==============================================================================

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
