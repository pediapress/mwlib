#! /usr/bin/env python

# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.

import os
import simplejson
import tempfile
import threading
import zipfile

from mwlib import uparser, parser, jobsched, metabook, mwapidb
import mwlib.log

# ==============================================================================

log = mwlib.log.Log("recorddb")

# ==============================================================================


class RecordDB(object):
    """Proxy getRawArticle() and getTemplate() to another WikiDB and record all
    results for later retrieval.
    """
    
    def __init__(self, db, articles, templates, sources):
        """
        @param db: WikiDB to use
        
        @param articles: dictionary to store article data
        @type articles: dict
        
        @param templates: dictionary to store template data
        @type templates: dict
        
        @param sources: dictionary to store source data
        @type sources: dict
        """
        
        assert db is not None, "db must not be None"
        self.db = db
        self.articles = articles
        self.templates = templates
        self.sources = sources
    
    def getRawArticle(self, name, revision=None):
        r = self.db.getRawArticle(name, revision=revision)
        if r is None:
            return None
        self.articles[name] = {
            'revision': revision,
            'content-type': 'text/x-wiki',
            'content': r,
            'url': self.db.getURL(name, revision=revision),
            'authors': self.db.getAuthors(name, revision=revision),
        }
        if hasattr(self.db, 'getSource'):
            src  = self.db.getSource(name, revision=revision)
            if src and 'url' in src:
                self.articles[name]['source-url'] = src['url']
                if src['url'] not in self.sources:
                    self.sources[src['url']] = src
        return r
    
    def getTemplate(self, name, followRedirects=False):
        try:
            return self.templates[name]['content']
        except KeyError:
            pass
        r = self.db.getTemplate(name, followRedirects=followRedirects)
        self.templates[name] = {
            'content-type': 'text/x-wiki',
            'content': r,
        }
        return r
    
    def getSource(self, title, revision=None):
        return self.db.getSource(title, revision=revision)
    

# ==============================================================================


class ZipfileCreator(object):
    """Create ZIP files usable as WikiDB
    
    See docs/zipfile.txt
    """
    
    def __init__(self, zf,
        imagesize=None,
        num_article_threads=3,
        num_image_threads=5,
    ):
        """
        @param imagesize: max. size of images
        @type imagesize: int
        
        @param num_article_threads: number of threads for parallel article
            fetching & parsing (set to 0 to turn threading off)
        @type num_article_threads: int
        
        
        @param num_image_threads: number of threads for parallel image fetching
            (set to 0 to turn threading off)
        @type num_image_threads: int
        """
        
        self.zf = zf
        self.imagesize = imagesize
        self.articles = {}
        self.templates = {}
        self.sources = {}
        self.images = {}
        self.zf_lock = threading.RLock()
        if num_article_threads > 0:
            self.article_adders = jobsched.JobScheduler(num_article_threads)
        else:
            self.article_adders = None
        if num_image_threads > 0:
            self.image_fetchers = jobsched.JobScheduler(num_image_threads)
        else:
            self.image_fetchers = None
    
    def addObject(self, name, value):
        """Add a file with name and contents value to the ZIP file
        
        @param name: name for entry in ZIP file, will be UTF-8 encoded
        @type name: unicode
        
        @param value: content for ZIP file entry
        @type value: str
        """
        
        self.zf.writestr(name.encode('utf-8'), value)
    
    def addArticle(self, title,
        revision=None,
        wikidb=None,
        imagedb=None,
        callback=None,
    ):
        """Add article with given title and revision to ZIP file. This will add
        all referenced templates and images, too.
        
        @param title: article title
        @type title: unicode
        
        @param revision: article revision (optional)
        @type revision: int
        
        @param wikidb: WikiDB to use
        
        @param imagedb: ImageDB to use (optional)
        
        @param callback: callable which is called when article is parsed (optional)
        @type callback: callable with signature callback(title) -> None
        """
        
        if title in self.articles:
            return
        self.articles[title] = {}
        
        def add_article_job(title):
            recorddb = RecordDB(wikidb, self.articles, self.templates, self.sources)
            raw = recorddb.getRawArticle(title, revision=revision)
            if raw is None:
                log.warn('Could not get article %r' % title)
                return
            self.parseArticle(title,
                revision=revision,
                raw=raw,
                wikidb=wikidb,
                imagedb=imagedb,
            )
            if callback is not None:
                callback(title)
        
        if self.article_adders is not None:
            self.article_adders.add_job(title, add_article_job)
        else:
            add_article_job(title)
    
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
        
        recorddb = RecordDB(wikidb, self.articles, self.templates, self.sources)
        parse_tree = uparser.parseString(title,
            revision=revision,
            raw=raw,
            wikidb=recorddb,
        )
        if imagedb is None:
            return
        for node in parse_tree.allchildren():
            if isinstance(node, parser.ImageLink):
                self.addImage(node.target, imagedb=imagedb)
    
    def addImage(self, name, imagedb=None):
        """Add image with given name to the ZIP file
        
        @param name: image name
        @type name: uncidoe
        
        @param imagedb: ImageDB to use
        """
        
        if name in self.images:
            return
        self.images[name] = {}
        
        def fetch_image_job(name):
            path = imagedb.getDiskPath(name, size=self.imagesize)
            if path is None:
                log.warn('Could not get image %r' % name)
                return
            self.zf_lock.acquire()
            try:
                zipname = u"images/%s" % name.replace("'", '-')
                self.zf.write(path, zipname.encode("utf-8"))
            finally:
                self.zf_lock.release()
            self.images[name]['url'] = imagedb.getURL(name, size=self.imagesize)
            descriptionurl = imagedb.getDescriptionURL(name)
            if descriptionurl:
                self.images[name]['descriptionurl'] = descriptionurl
            license = imagedb.getLicense(name)
            if license:
                self.images[name]['license'] = license
            
        if self.image_fetchers is not None:
            self.image_fetchers.add_job(name, fetch_image_job)
        else:
            fetch_image_job(name)
    
    def writeContent(self):
        """Finish ZIP file by writing the actual content"""
        
        if self.article_adders is not None:
            # wait for articles first (they add images)...
            self.article_adders.join()
        if self.image_fetchers is not None:
            # ... then for the images
            self.image_fetchers.join()
        self.addObject('content.json', simplejson.dumps(dict(
            articles=self.articles,
            templates=self.templates,
            sources=self.sources,
            images=self.images,
        )))
    

# ==============================================================================


def make_zip_file(output, env,
    set_progress=None,
    set_current_article=None,
    num_article_threads=3,
    num_image_threads=5,
    imagesize=800,
):
    set_progress = set_progress or (lambda p: None)
    set_current_article = set_current_article or (lambda t: None)
    
    if output is None:
        fd, output = tempfile.mkstemp(suffix='.zip')
        os.close(fd)
    
    fd, tmpzip = tempfile.mkstemp(suffix='.zip', dir=os.path.dirname(output))
    os.close(fd)
    zf = zipfile.ZipFile(tmpzip, 'w')
    
    z = ZipfileCreator(zf,
        imagesize=imagesize,
        num_article_threads=num_article_threads,
        num_image_threads=num_image_threads,
    )
    
    articles = metabook.get_item_list(env.metabook, filter_type='article')
    if articles:
        class IncProgress(object):
            inc = 100./len(articles)
            p = 0
            def __call__(self, title):
                self.p += self.inc
                set_progress(int(self.p))
                set_current_article(title)
        inc_progress = IncProgress()
    else:
        inc_progress = None
    
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
            callback=inc_progress,
        )
    
    for license in env.get_licenses():
        z.parseArticle(
            title=license['title'],
            raw=license['wikitext'],
            wikidb=env.wiki,
            imagedb=env.images,
        )
    
    z.addObject('metabook.json', simplejson.dumps(env.metabook))
    
    z.writeContent()
    zf.close()
    if os.path.exists(output):
        os.unlink(output)
    os.rename(tmpzip, output)
    
    if env.images and hasattr(env.images, 'clear'):
        env.images.clear()
    
    set_progress(100)
    return output
