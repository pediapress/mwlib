#! /usr/bin/env python

# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.

import simplejson
import zipfile

from mwlib import uparser, parser, mwapidb
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
        r = self.db.getTemplate(name, followRedirects=followRedirects)
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
    
    def addObject(self, name, value):
        """
        @type name: unicode
        
        @type value: str
        """
        
        self.zf.writestr(name.encode('utf-8'), value)
    
    def addArticle(self, title, revision=None, wikidb=None, imagedb=None):
        recorddb = RecordDB(wikidb, self.articles, self.templates)
        raw = recorddb.getRawArticle(title, revision=revision)
        if raw is None:
            return
        self.articles[title] = {
            'revision': revision,
            'content-type': 'text/x-wiki',
            'content': raw,
            'url': wikidb.getURL(title, revision=revision),
            'authors': wikidb.getAuthors(title, revision=revision),
        }
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
        self.images[name] = {}
        path = imagedb.getDiskPath(name, size=self.imagesize)
        if path is None:
            log.warn('Could not get image %r (size=%r)' % (name, self.imagesize))
            return
        self.zf.write(path, (u"images/%s" % name.replace("'", '-')).encode("utf-8"))
        self.images[name]['url'] = imagedb.getURL(name, size=self.imagesize)
        try:
            descriptionurl = imagedb.getDescriptionURL(name)
            if descriptionurl:
                self.images[name]['descriptionurl'] = descriptionurl
        except AttributeError: # FIXME: implement getDescriptionURL() in all ImageDBs and remove this try-except
            pass
        license = imagedb.getLicense(name)
        if license:
            self.images[name]['license'] = license
    
    def writeContent(self):
        self.addObject('content.json', simplejson.dumps(dict(
            articles=self.articles,
            templates=self.templates,
            images=self.images,
        )))
    
