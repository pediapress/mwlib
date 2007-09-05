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
        
    def getRawArticle(self, name):
        r = self.db.getRawArticle(name)
        self.articles[name] = r
        return r

    def getTemplate(self, name, followRedirects=False):
        r = self.db.getTemplate(name, followRedirects=followRedirects)
        self.templates[name] = r
        return r

    
class ZipfileCreator(object):
    def __init__(self, wikidb=None, imgdb=None):
        self.db = RecordDB(wikidb)
        self.images = set()
        self.imgdb = imgdb

    def addArticle(self, title):
        a=uparser.parseString(title, wikidb=self.db)
        log.info("searching for images")
        for x in a.allchildren():
            if isinstance(x, parser.ImageLink):
                self.images.add(x.target)
                log.info("found", x.target)


    def _writeImages(self, zf):
        if self.imgdb is None:
            return
            
        images = list(self.images)
        images.sort()
        for i in images:
            dp = self.imgdb.getDiskPath(i)
            if dp:
                zf.write(dp, (u"images/%s" % i).encode("utf-8"))
            print i, dp
            

    def createArchive(self, name):
        zf = zipfile.ZipFile(name, "w", compression=zipfile.ZIP_DEFLATED)
        contents = simplejson.dumps(dict(articles=self.db.articles, templates=self.db.templates))
        zf.writestr("contents.json", contents)
        self._writeImages(zf)
        zf.close()
        
        
