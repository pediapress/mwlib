#! /usr/bin/env python

# Copyright (c) 2007, PediaPress GmbH
# See README.txt for additional licensing information.

import collections
import os
import simplejson
import tempfile
import zipfile

from mwlib.metabook import MetaBook

class Wiki(object):
    def __init__(self, path):
        self.zf = zipfile.ZipFile(path)
        mb = MetaBook()
        mb.loadJson(self.zf.read("collection.json"))
        self.articles = collections.defaultdict(list)
        for item in mb.getItems():
            if item['type'] != 'article':
                continue
            self.articles[item['title']].append(item)
        self.templates = {}
    
    def _getArticle(self, title, revision=None):
        articles = sorted(self.articles[title], key=lambda item: item.get('revision', None), reverse=True)
        if not articles:
            return None
        if revision is None:
            return articles[0]
        for article in articles:
            if article.get('revision', None) == revision:
                return article
        return None
    
    def getRawArticle(self, title, revision=None):
        article = self._getArticle(title, revision=revision)
        if article:
            return article['content']
    
    def getURL(self, title, revision=None):
        article = self._getArticle(title, revision=revision)
        if article:
            return article['url']
    
    def getTemplate(self, name, followRedirects=True):
        return self.templates[name]
    

class ImageDB(object):
    def __init__(self, zipfilename, tmpdir=None):
        self.zf = zipfile.ZipFile(zipfilename)
        self._tmpdir = tmpdir
        mb = MetaBook()
        mb.loadJson(self.zf.read('collection.json'))
        self.imageMap = mb.imageMap
    
    @property
    def tmpdir(self):
        if self._tmpdir is None:
            self._tmpdir = unicode(tempfile.mkdtemp())
        return self._tmpdir

    def getDiskPath(self, name):
        try:
            data = self.zf.read(self.imageMap[name].encode('utf-8'))
        except KeyError: # no such file
            return None
        
        res = os.path.join(self.tmpdir, name)
        f=open(res, "wb")
        f.write(data)
        f.close()
        return res


