#! /usr/bin/env python

# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.

import simplejson
import zipfile

from mwlib import uparser, parser, mwapidb, jobsched, utils
import mwlib.log

log = mwlib.log.Log("recorddb")


class RecordDB(object):
    def __init__(self, db, articles, templates):
        assert db is not None, "db must not be None"
        self.db = db
        self.articles = articles
        self.templates = templates
        
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
        return r
    
    def getTemplate(self, name, followRedirects=False):
        try:
            return self.templates[name]['content']
        except KeyError:
            pass
        r = self.db.getTemplate(name, followRedirects=followRedirects)
        if r is None:
            return
        self.templates[name] = {
            'content-type': 'text/x-wiki',
            'content': r,
        }
        return r
    

class ZipfileCreator(object):
    def __init__(self, zf, imagesize=None):
        self.zf = zf
        self.imagesize = imagesize
        self.articles = {}
        self.templates = {}
        self.images = {}
        self.fetcher = jobsched.JobScheduler(5, utils.fetch_url)
        self.adder = jobsched.JobScheduler(5, self._addArticleJob)
    
    def addObject(self, name, value):
        """
        @type name: unicode
        
        @type value: str
        """
        
        self.zf.writestr(name.encode('utf-8'), value)
    
    def addArticle(self, title, revision=None, wikidb=None, imagedb=None):
        self.adder.add_job((title, revision), wikidb=wikidb, imagedb=imagedb)
    
    def _addArticleJob(self, title_revision, wikidb=None, imagedb=None):
        title, revision = title_revision
        recorddb = RecordDB(wikidb, self.articles, self.templates)
        raw = recorddb.getRawArticle(title, revision=revision)
        if raw is None:
            return
        self.parseArticle(title, revision=revision, raw=raw, wikidb=wikidb, imagedb=imagedb)
    
    def parseArticle(self, title, revision=None, raw=None, wikidb=None, imagedb=None):
        recorddb = RecordDB(wikidb, self.articles, self.templates)
        parse_tree = uparser.parseString(title, revision=revision, raw=raw, wikidb=recorddb)
        if imagedb is None:
            return
        for node in parse_tree.allchildren():
            if isinstance(node, parser.ImageLink):
                self.addImage(node.target, imagedb=imagedb)
    
    def addImage(self, name, imagedb=None):
        if name in self.images:
            return
        self.images[name] = {} # create dict entry as fast as possible
        self.images[name]['url'] = imagedb.getURL(name, size=self.imagesize)
        self.images[name]['diskpath'] = imagedb.getDiskPath(name,
            size=self.imagesize,
            fetcher=self.fetcher,
        )
        if hasattr(imagedb, 'getDescriptionURL'): # FIXME: implement in all ImageDBs
            descriptionurl = imagedb.getDescriptionURL(name)
            if descriptionurl:
                self.images[name]['descriptionurl'] = descriptionurl
        license = imagedb.getLicense(name)
        if license:
            self.images[name]['license'] = license
    
    def writeContent(self):
        # first wait for all articles to be parsed (they add images)...
        self.adder.get_results()
        # ... then wait for the images to be fetched
        results = self.fetcher.get_results()
        for name, attrs in self.images.items():
            if results[attrs['url']] is None:
                log.warn('Could not get image %r (size=%r)' % (name, self.imagesize))
                continue
            self.zf.write(attrs['diskpath'], (u"images/%s" % name.replace("'", '-')).encode("utf-8"))
            del attrs['diskpath']
        self.addObject('content.json', simplejson.dumps(dict(
            articles=self.articles,
            templates=self.templates,
            images=self.images,
        )))
    
