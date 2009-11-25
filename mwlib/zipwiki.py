#! /usr/bin/env python

# Copyright (c) 2007-2009 PediaPress GmbH
# See README.txt for additional licensing information.

import os
import shutil
import tempfile
from zipfile import ZipFile
import urlparse
from mwlib import myjson as json, metabook, nshandling

def normalize_title(title):
    if not title:
        return title
    if not isinstance(title, unicode):
        title = unicode(title, 'utf-8')
    title = title.replace('_', ' ')
    title = title[0].upper() + title[1:]
    return title

def nget(d, key):
    try:
        return d[key]
    except KeyError:
        return d[normalize_title(key)]

class page(object):
    source_url = None
    authors = None
    
    def __init__(self, **kw):
        self.__dict__.update(kw)
        

class ZipWikiBase(object):
    def __init__(self, zipfile):
        """
        @type zipfile: basestring or ZipFile
        """

        if hasattr(zipfile, "read"):
            self.zf = zipfile
        else:
            self.zf = ZipFile(zipfile)

        self.metabook = json.loads(unicode(self.zf.read("metabook.json"), 'utf-8'))
        content = json.loads(unicode(self.zf.read('content.json'), 'utf-8'))
        
        
        self.images = content.get('images', {})
        self.sources = content.get('sources', {})
        self.licenses = content.get('licenses', None)
        self.siteinfo = content.get('siteinfo', None)
        self.nshandler = nshandling.nshandler(self.get_siteinfo())

        self.pages = {}

        def addpages(name2val, defaultns):        
            for title, vals in name2val.items():
                title = self.nshandler.get_fqname(title, defaultns)

                fixed = {}
                for k, v in vals.items():
                    k=str(k).replace("-",  "_")
                    if k=="content":
                        k="rawtext"
                    fixed[k]=v
                    
                self.pages[title] = page(**fixed)

        addpages(content.get('templates', {}), 10)
        addpages(content.get('articles', {}), 0)

    def get_siteinfo(self):
        if self.siteinfo is not None:
            return self.siteinfo

        from mwlib.siteinfo import get_siteinfo
        if self.sources:
            self.siteinfo = get_siteinfo(self.sources.values()[0].language or "en")
        else:
            self.siteinfo = get_siteinfo('en')
        return self.siteinfo


class Wiki(ZipWikiBase):
    def normalize_and_get_page(self, title, defaultns):
        fqname = self.nshandler.get_fqname(title, defaultns)
        return self.pages.get(fqname, None)
        
    def getSource(self, title, revision=None):
        """Return source for article with given title and revision
        
        @param title: article title
        @type title: unicode
        
        @param revision: article revision (optional)
        @type revision: unicode
        """

        page = self.normalize_and_get_page(title, 0)
        if page is None:
            return None
        return self.sources[page.source_url]

    def getInterwikiMap(self, title, revision=None):
        """Return interwikimap for given article and revision
        
        @returns: interwikimap, i.e. dict mapping prefixes to interwiki data
        @rtype: dict
        """
        
        source = self.getSource(title, revision=revision)
        if source is None:
            return None
        return source.get('interwikimap', None)
    
    def getURL(self, title, revision=None):
        fqname = self.nshandler.get_fqname(title, 0)
        baseurl = self.sources.values()[0].base_url
        return "%s/index.php?title=%s" % (baseurl, title)
    
    def getAuthors(self, title, revision=None):
        page = self.normalize_and_get_page(title, 0)
        if page is None:
            return None
        
        return page.authors or []

    def getLicenses(self):
        if self.licenses is None:
            # ZIP file of old mwlib version does not contain licenses...
            try:
                self.licenses = metabook.get_licenses(self.metabook)
            except Exception:
                self.licenses = []

                
        for i, x in enumerate(self.licenses):
            if isinstance(x, dict):
                x=self.licenses[i] = metabook.license(title=x.get("title"), wikitext=x.get("wikitext"))
                
            x._wiki = self
            
        return self.licenses
    
    def getParsedArticle(self, title, revision=None):
        page = self.normalize_and_get_page(title, 0)
        if page:
            raw = page.rawtext
        else:
            raw = None
        
        if raw is None:
            return None

        
        lang = None
        source = self.getSource(title, revision=revision)
        
        if source is not None:
            lang = source.language
        from mwlib import uparser
        
        return uparser.parseString(title=title, raw=raw, wikidb=self, lang=lang)
  

class ImageDB(ZipWikiBase):
    def __init__(self, zipfile, tmpdir=None):
        super(ImageDB, self).__init__(zipfile)
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
        ns, partial, full = self.nshandler.splitname(name, defaultns=nshandling.NS_FILE)
        try:
            return self.diskpaths[partial]
        except KeyError:
            pass
        try:
            fname = name[name.find(":") + 1:].replace("'", '-').replace('_',' ')            
            data = self.zf.read('images/%s' % fname.encode('utf-8'))
        except (KeyError,  IOError): # no such file
            return None        
        try:
            ext = '.' + partial.rsplit('.', 1)[1]
        except IndexError:
            ext = ''
        if ext.lower() == '.svg':
            ext = '.svg.png'
        elif ext.lower() == '.gif':
            ext = '.gif.png'
        res = os.path.join(self.tmpdir, 'image%06d%s' % (len(self.diskpaths), ext))
        assert not os.path.exists(res), "file %r already exists" % res
        self.diskpaths[partial] = res
        open(res, "wb").write(data)
        return res
    
    def getImageTemplates(self, name, wikidb=None):
        ns, partial, full = self.nshandler.splitname(name, defaultns=nshandling.NS_FILE)
        try:
            return nget(self.images, partial)['templates']
        except KeyError:
            return []

    getImageWords=getImageTemplates

    
    def getContributors(self, name, wikidb=None):
        ns, partial, full = self.nshandler.splitname(name, defaultns=nshandling.NS_FILE)
        try:
            return nget(self.images, partial)['contributors']
        except KeyError:
            return []
    
    def getURL(self, name, size=None):
        ns, partial, full = self.nshandler.splitname(name, defaultns=nshandling.NS_FILE)
        try:
            return nget(self.images, partial)['url']
        except KeyError:
            return None
    
    def getDescriptionURL(self, name):
        ns, partial, full = self.nshandler.splitname(name, defaultns=nshandling.NS_FILE)
        try:
            return nget(self.images, partial)['descriptionurl']
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
