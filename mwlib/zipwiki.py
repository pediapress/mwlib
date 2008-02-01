#! /usr/bin/env python

# Copyright (c) 2008, PediaPress GmbH
# See README.txt for additional licensing information.

import base64
import os
import pickle
import shutil
import simplejson
import tempfile
from zipfile import ZipFile

from mwlib.metabook import MetaBook

class Wiki(object):
    def __init__(self, zipfile):
        """
        @type zipfile: basestring or ZipFile
        """
        
        if isinstance(zipfile, ZipFile):
            self.zf = zipfile
        else:
            self.zf = ZipFile(zipfile)
        self.metabook = MetaBook()
        self.metabook.loadJson(self.zf.read("metabook.json"))
        content = simplejson.loads(self.zf.read('content.json'))
        self.articles = content['articles']
        self.templates = content['templates']
    
    def _getArticle(self, title, revision=None):
        try:
            article = self.articles[title]
            if revision is None or article['revision'] == revision:
                return article
        except KeyError:
            pass
        return None
    
    def getRawArticle(self, title, revision=None):
        article = self._getArticle(title, revision=revision)
        if article:
            return article['content']
        return None
    
    def getParsedArticle(self, title, revision=None):
        article = self._getArticle(title, revision=revision)
        if article:
            return pickle.loads(base64.b64decode(article['parsetree']))
        return None
    
    def getURL(self, title, revision=None):
        article = self._getArticle(title, revision=revision)
        if article:
            return article['url']
        return None
    
    def getTemplate(self, name, followRedirects=True):
        try:
            return self.templates[name]['content']
        except KeyError:
            pass
        return None
    
    def getImageMetaInfos(self, imgname):
        return {}

    
class ImageDB(object):
    def __init__(self, zipfile, tmpdir=None):
        """
        @type zipfile: basestring or ZipFile
        """
        
        if isinstance(zipfile, ZipFile):
            self.zf = zipfile
        else:
            self.zf = ZipFile(zipfile)
        content = simplejson.loads(self.zf.read('content.json'))
        self.images = content['images']
        self._tmpdir = tmpdir
        self.diskpaths = {}
    
    @property
    def tmpdir(self):
        if self._tmpdir is None:
            self._tmpdir = unicode(tempfile.mkdtemp())
        return self._tmpdir
    
    def getDiskPath(self, name, size=None):
        try:
            return self.diskpaths[name]
        except KeyError:
            pass
        try:
            data = self.zf.read('images/%s' % name.encode('utf-8'))
        except KeyError: # no such file
            return None
        
        try:
            ext = '.' + name.rsplit('.', 1)[1]
        except IndexError:
            ext = ''
        res = os.path.join(self.tmpdir, 'image%04d%s' % (len(self.diskpaths), ext))
        self.diskpaths[name] = res
        f=open(res, "wb")
        f.write(data)
        f.close()
        return res
    
    def getPath(self):
        raise NotImplemented('getPath() does not work with zipwiki.ImageDB!')
    
    def getURL(self, name):
        try:
            return self.images[name]['url']
        except KeyError:
            None
    
    def clean(self):
        if self._tmpdir:
            shutil.rmtree(self._tmpdir, ignore_errors=True)
    
