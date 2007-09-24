#! /usr/bin/env python

# Copyright (c) 2007, PediaPress GmbH
# See README.txt for additional licensing information.

import simplejson
import zipfile
from mwlib import uparser, parser
import mwlib.log
log = mwlib.log.Log("zip")


class RecordDB(object):
    def __init__(self, db):
        assert db is not None, "db must not be None"
        self.db = db
        self.articles = {}
        self.templates = {}
        
    def getRawArticle(self, name, revision=None):
        r = self.db.getRawArticle(name, revision=revision)
        self.articles[name] = {
            'revision': revision,
            'contenttype': 'text/x-mediawiki',
            'content': r,
            'url': self.db.getURL(name, revision=revision),
        }
        return r

    def getTemplate(self, name, followRedirects=False):
        r = self.db.getTemplate(name, followRedirects=followRedirects)
        self.templates[name] = {'contenttype': 'text/x-mediawiki', 'content': r}
        return r

    
class ZipfileCreator(object):
    def __init__(self, zf, wikidb=None, imgdb=None):
        self.zf = zf
        self.db = RecordDB(wikidb)
        self.images = set()
        self.imgdb = imgdb

    def addObject(self, name, value):
        """
        @type name: unicode
        
        @type value: str
        """
        
        zf.writestr(name.encode('utf-8'), value)
    
    def addArticle(self, title, revision=None):
        a=uparser.parseString(title, revision=revision, wikidb=self.db)
        log.info("searching for images")
        for x in a.allchildren():
            if isinstance(x, parser.ImageLink):
                self.images.add(x.target)
                log.info("found", x.target)

    def writeImages(self, width=None):
        if self.imgdb is None:
            return
            
        images = list(self.images)
        images.sort()
        image_map = {}
        for i in images:
            dp = self.imgdb.getDiskPath(i, width=width)
            if dp:
                self.zf.write(dp, (u"images/%s" % i).encode("utf-8"))
    
    def writeContent(self):
        self.addObject('content.json', simplejson.dumps(dict(
            articles=self.db.articles,
            templates=self.db.templates,
        )))
        
        
