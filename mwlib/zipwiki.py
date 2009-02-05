#! /usr/bin/env python

# Copyright (c) 2008, PediaPress GmbH
# See README.txt for additional licensing information.

import os
import shutil
import tempfile
from zipfile import ZipFile
import urlparse
try:
    import json
except ImportError:
    import simplejson as json

from mwlib import wikidbbase, namespace

class Wiki(wikidbbase.WikiDBBase):
    def __init__(self, zipfile):
        """
        @type zipfile: basestring or ZipFile
        """
        
        if isinstance(zipfile, ZipFile):
            self.zf = zipfile
        else:
            self.zf = ZipFile(zipfile)
        self.metabook = json.loads(self.zf.read("metabook.json"))
        content = json.loads(self.zf.read('content.json'))
        self.articles = content.get('articles', {})
        self.templates = content.get('templates', {})
        self.sources = content.get('sources', {})
    
    def _getArticle(self, title, revision=None):
        try:
            article = self.articles[title]
            if revision is None or article['revision'] == revision:
                return article
        except KeyError:
            pass
        return None
    
    def getSource(self, title, revision=None):
        """Return source for article with given title and revision
        
        @param title: article title
        @type title: unicode
        
        @param revision: article revision (optional)
        @type revision: unicode
        """
        
        article = self._getArticle(title, revision=revision)
        if article is None:
            return None
        try:
            return self.sources[article['source-url']]
        except KeyError:
            return None
    
    def getInterwikiMap(self, title, revision=None):
        """Return interwikimap for given article and revision
        
        @returns: interwikimap, i.e. dict mapping prefixes to interwiki data
        @rtype: dict
        """
        
        source = self.getSource(title, revision=revision)
        if source is None:
            return None
        return source.get('interwikimap', None)
    
    def getRawArticle(self, title, revision=None):
        ns, partial, full = namespace.splitname(title)
        if ns==namespace.NS_TEMPLATE:
            return self.getTemplate(partial)
        article = self._getArticle(title, revision=revision)
        if article:
            result = article['content']
            if isinstance(result, str): # fix bug in some simplejson version w/ Python 2.4
                return unicode(result, 'utf-8')
            return result
        return None
    
    def getURL(self, title, revision=None):
        article = self._getArticle(title, revision=revision)
        if article:
            return article['url']
        return None
    
    def getAuthors(self, title, revision=None):
        article = self._getArticle(title, revision=revision)
        if article:
            return article.get('authors', [])
        return None
    
    def getTemplate(self, name, followRedirects=True):
        ns, name, full = namespace.splitname(name, namespace.NS_TEMPLATE)
        if ns!=namespace.NS_TEMPLATE:
            return self.getRawArticle(full)
        
        
        try:
            result = self.templates[name]['content']
            if isinstance(result, str): # fix bug in some simplejson version w/ Python 2.4
                return unicode(result, 'utf-8')
            return result
        except KeyError:
            pass
        return None
    

class ImageDB(object):
    def __init__(self, zipfile, tmpdir=None):
        """
        @type zipfile: basestring or ZipFile
        """
        
        if isinstance(zipfile, ZipFile):
            self.zf = zipfile
        else:
            self.zf = ZipFile(zipfile)
        content = json.loads(self.zf.read('content.json'))
        self.images = content['images']
        self._tmpdir = tmpdir
        self.diskpaths = {}
    
    def clear(self):
        if self._tmpdir is not None:
            shutil.rmtree(self._tmpdir)
    
    @property
    def tmpdir(self):
        if self._tmpdir is None:
            self._tmpdir = unicode(tempfile.mkdtemp())
        return self._tmpdir

    def getPath(self, name, size=None):
        url = self.getURL(name, size=size)
        if url is None:
            return
        path = urlparse.urlparse(url)[2]
        pos = path.find('/thumb/')
        if pos >= 0:
            return path[pos + 1:]
        if path.count('/') >= 4:
            prefix, repo, hash1, hash2, name = url.rsplit('/', 4)
            return '%s/%s/%s/%s' % (repo, hash1, hash2, name)
        return path
    
    def getDiskPath(self, name, size=None):
        try:
            return self.diskpaths[name]
        except KeyError:
            pass
        try:
            data = self.zf.read('images/%s' % name.replace("'", '-').encode('utf-8'))
        except KeyError: # no such file
            return None
        
        try:
            ext = '.' + name.rsplit('.', 1)[1]
        except IndexError:
            ext = ''
        if ext.lower() == '.svg':
            ext = '.svg.png'
        elif ext.lower() == '.gif':
            ext = '.gif.png'
        res = os.path.join(self.tmpdir, 'image%04d%s' % (len(self.diskpaths), ext))
        self.diskpaths[name] = res
        f=open(res, "wb")
        f.write(data)
        f.close()
        return res
    
    def getImageTemplates(self, name, wikidb=None):
        try:
            return self.images[name]['templates']
        except KeyError:
            return []
    
    def getContributors(self, name, wikidb=None):
        try:
            return self.images[name]['contributors']
        except KeyError:
            return []
    
    def getPath(self):
        raise NotImplemented('getPath() does not work with zipwiki.ImageDB!')
    
    def getURL(self, name, size=None):
        try:
            return self.images[name]['url']
        except KeyError:
            return None
    
    def getDescriptionURL(self, name):
        try:
            return self.images[name]['descriptionurl']
        except KeyError:
            return None
    
    def clean(self):
        if self._tmpdir:
            shutil.rmtree(self._tmpdir, ignore_errors=True)
    



class FakeImageDB(ImageDB):

    imagedata = '\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x03 \x00\x00\x01\xe0\x01\x03\x00\x00\x00g\xc9\x9b\xb6\x00\x00\x00\x01sRGB\x00\xae\xce\x1c\xe9\x00\x00\x00\x06PLTE\xff\xff\xff\x00\x00\x00U\xc2\xd3~\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00EIDATx\xda\xed\xc1\x01\x01\x00\x00\x00\x82 \xff\xafnH@\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00/\x06\xbd`\x00\x01`<5\x84\x00\x00\x00\x00IEND\xaeB`\x82'

    def __init__(self, tmpdir=None):
        """
        @type zipfile: basestring or ZipFile
        """
        self._tmpdir = tmpdir        
    
    def getDiskPath(self, name, size=None):
        res = os.path.join(self.tmpdir, 'blank.png')
        if not os.path.exists(res):
            open(res, "w").write(self.imagedata)
        return res
    
    def getPath(self):
        raise NotImplemented('getPath() does not work with zipwiki.FakeImageDB!')
    
    def getURL(self, name):
        raise NotImplemented('getURL() does not work with zipwiki.FakeImageDB!')
    
    def getDescriptionURL(self, name):
        raise NotImplemented('getDescriptionURL() does not work with zipwiki.FakeImageDB!')
    
    def getImageTemplates(self, name, wikidb=None):
        raise NotImplemented('getImageTemplates() does not work with zipwiki.FakeImageDB!')
    


