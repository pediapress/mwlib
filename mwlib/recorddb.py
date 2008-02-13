#! /usr/bin/env python

# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.

import base64
import pickle
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
        self.templates[name] = {
            'contenttype': 'text/x-mediawiki',
            'content': r,
        }
        return r
    

class ZipfileCreator(object):
    def __init__(self, zf, wikidb=None, imgdb=None):
        self.zf = zf
        self.db = RecordDB(wikidb)
        self.images = {}
        self.imgdb = imgdb

    def addObject(self, name, value):
        """
        @type name: unicode
        
        @type value: str
        """
        
        self.zf.writestr(name.encode('utf-8'), value)
    
    def addArticle(self, title, revision=None):
        a = uparser.parseString(title, revision=revision, wikidb=self.db)
        self.db.articles[title]['parsetree'] = base64.b64encode(pickle.dumps(a))
        for x in a.allchildren():
            if isinstance(x, parser.ImageLink):
                name = x.target
                self.images[name] = {}
    
    def writeImages(self, size=None):
        if self.imgdb is None:
            return
        
        for name in sorted(self.images.keys()):
            dp = self.imgdb.getDiskPath(name, size=size)
            if dp is None:
                continue
            self.zf.write(dp, (u"images/%s" % name).encode("utf-8"))
            self.images[name]['url'] = self.imgdb.getURL(name, size=size)
    
    def writeContent(self):
        self.addObject('content.json', simplejson.dumps(dict(
            articles=self.db.articles,
            templates=self.db.templates,
            images=self.images,
        )))
    
