#! /usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2008, PediaPress GmbH
# See README.txt for additional licensing information.

import os
import re
import shutil
import tempfile
import time
import urllib
import urllib2

import simplejson

from mwlib import uparser, utils
from mwlib.log import Log

# ==============================================================================

log = Log("mwapidb")

# ==============================================================================


class APIDBBase(object):
    def __init__(self, base_url):
        """Init ImageDB with a base URL
        
        @param base_url: base URL of a MediaWiki, i.e. URL path to php scripts,
            e.g. 'http://en.wikipedia.org/w/' for English Wikipedia.
        @type base_url: basestring
        """

        if isinstance(base_url, unicode):
            self.base_url = base_url.encode('ascii')
        else:
            self.base_url = base_url
        if self.base_url[-1] != '/':
            self.base_url += '/'
        self.api_url = '%sapi.php?' % self.base_url
        self.index_url = '%sindex.php?' % self.base_url
    
    def fetch_url(self, url):
        log.info("fetching %r" % (url,))
        opener = urllib2.build_opener()
        opener.addheaders = [('User-agent', 'mwlib')]
        try:
            data = opener.open(url).read()
        except urllib2.URLError, err:
            log.error("%s - while fetching %r" % (err, url))
            return None
        log.info("got %r (%d Bytes)" % (url, len(data)))
        return data
    
    def query(self, **kwargs):
        args = {
            'action': 'query',
            'format': 'json',
        }
        args.update(**kwargs)
        for k, v in args.items():
            if isinstance(v, unicode):
                args[k] = v.encode('utf-8')
        data = self.fetch_url('%s%s' % (self.api_url, urllib.urlencode(args)))
        if data is None:
            return None
        result = simplejson.loads(unicode(data, 'utf-8'))
        try:
            return result['query']
        except KeyError:
            return None
    

# ==============================================================================


class ImageDB(APIDBBase):
    def __init__(self, api_url):
        super(ImageDB, self).__init__(api_url)
        self.tmpdir = tempfile.mkdtemp()
    
    def clear(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
    
    def getURL(self, name, size=None):
        """Return image URL for image with given name
        
        @param name: image name (without namespace, i.e. without 'Image:')
        @type name: unicode
        
        @returns: URL to original image
        @rtype: str
        """
        
        assert isinstance(name, unicode), 'name must be of type unicode'
        
        if size is None:
            result = self.query(titles='Image:%s' % name, prop='imageinfo', iiprop='url')
        else:
            result = self.query(titles='Image:%s' % name, prop='imageinfo', iiprop='url', iiurlwidth=str(size))
        if result is None:
            return None
        try:
            if size is None:
                return result['pages'].values()[0]['imageinfo'][0]['url']
            else:
                return result['pages'].values()[0]['imageinfo'][0]['thumburl']
        except KeyError:
            return None
    
    def getDiskPath(self, name, size=None):
        """Return filename for image with given name and size
        
        @param name: image name (without namespace, i.e. without 'Image:')
        @type name: unicode
        
        @param size: if given, the image is converted to the given maximum width
        @type size: int or NoneType
        
        @returns: filename of image or None if image could not be found
        @rtype: basestring
        """
        
        assert isinstance(name, unicode), 'name must be of type unicode'
        
        url = self.getURL(name, size=size)
        if url is None:
            return None
        
        data = self.fetch_url(url)
        if url is None:
            return None
        
        ext = url.rsplit('.')[-1]
        if size is not None:
            ext = '%dpx.%s' % (size, ext)
        else:
            ext = '.%s' % ext
        filename = os.path.join(self.tmpdir, utils.fsescape(name + ext))
        f = open(filename, 'wb')
        f.write(data)
        f.close()
        return filename
    
    def getImageDescription(self, name):
        result = self.query(titles='Image:%s' % name, prop='imageinfo', iiprop='comment')
        if result is None:
            return None
        try:
            return result['pages'].values()[0]['imageinfo']['comment']
        except KeyError:
            return None
    
    def getLicense(self, name):
        """Return license of image as stated on image description page
        
        @param name: image name without namespace (e.g. without "Image:")
        @type name: unicode
        
        @returns: license of image of None, if no valid license could be found
        @rtype: unicode
        """
        
        assert isinstance(name, unicode), 'name must be of type unicode'
        
        descr = self.getImageDescription(name)
        if descr is None:
            return None
        
        return u'FIXME!!!'
    

# ==============================================================================
    
def normname(name):
    name = name.strip().replace("_", " ")
    name = name[:1].upper()+name[1:]
    return name


class WikiDB(APIDBBase):
    redirect_rex = re.compile(r'^#Redirect:?\s*?\[\[(?P<redirect>.*?)\]\]', re.IGNORECASE)
    print_template = 'Template:Print%s'
    
    def __init__(self, api_url, templateblacklist=None, defaultauthors=None):
        """
        @param defaultauthors: list of default (principal) authors for articles
        @type defaultauthors: [unicode]
        """
        
        super(WikiDB, self).__init__(api_url)
        
        if templateblacklist:
            self.templateblacklist = self._readTemplateBlacklist(templateblacklist)
        else:
            self.templateblacklist = []
        
        if defaultauthors:
            self.defaultauthors = defaultauthors
        else:
            self.defaultauthors = []
        
        self.pages = {}
    
    def _readTemplateBlacklist(self, templateblacklist):
        if not templateblacklist:
            return []
        try:
            content = self.getRawArticle(templateblacklist)
            return [template.lower().strip() for template in re.findall('\* *\[\[.*?:(.*?)\]\]', content)]
        except: # fixme: more sensible error handling...
            log.error('Error fetching template blacklist from url:', templateblacklist)
            return []
    
    def getURL(self, title, revision=None):
        name = urllib.quote(title.replace(" ", "_").encode('utf-8'))
        if revision is None:
            return '%stitle=%s' % (self.index_url, name)
        else:
            return '%stitle=%s&oldid=%s' % (self.index_url, name, revision)
    
    def getAuthors(self, title, revision=None):
        return list(self.defaultauthors)
    
    def getTemplate(self, name, followRedirects=False):
        if ":" in name:
            name = name.split(':', 1)[1]
        
        if name.lower() in self.templateblacklist:
            log.info("ignoring blacklisted template:" , repr(name))
            return None
        
        for title in (self.print_template % name, 'Template:%s' % name):
            log.info("Trying template %r" % (title,))
            c = self.getRawArticle(title)
            if c is None:
                continue
            mo = self.redirect_rex.search(c)
            if mo is None:
                return c
            redirect = mo.group('redirect')
            redirect = normname(redirect.split("|", 1)[0].split("#", 1)[0])
            return self.getTemplate(redirect)
        
        return None
    
    def getRawArticle(self, title, revision=None):
        if revision is None:
            result = self.query(titles=title, prop='revisions', rvprop='content')
        else:
            result = self.query(revids=revision, prop='revisions', rvprop='content')
        if result is None:
            return None
        try:
            page = result['pages'].values()[0]
            if page['title'] != title:
                return None
            return page['revisions'][0].values()[0]
        except KeyError:
            return None
    
    def getParsedArticle(self, title, revision=None):
        raw = self.getRawArticle(title, revision=revision)
        if raw is None:
            return None
        a = uparser.parseString(title=title, raw=raw, wikidb=self)
        return a


class Overlay(WikiDB):
    def __init__(self, wikidb, templates):
        self.__dict__.update(wikidb.__dict__)
        self.overlay_templates = templates
        
    def getTemplate(self, name, followRedirects=False):
        try:
            return self.overlay_templates[name]
        except KeyError:
            pass
        
        return super(Overlay, self).getTemplate(name, followRedirects=followRedirects)
    
