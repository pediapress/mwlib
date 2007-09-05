#! /usr/bin/env python

# Copyright (c) 2007, PediaPress GmbH
# See README.txt for additional licensing information.

## http://mw/index.php?title=Image:Bla.jpg&action=raw
## http://mw/index.php?title=Template:MYHEADER&action=raw


import os

import urllib
import urllib2
import md5
import time

from mwlib import uparser
from mwlib.log import Log

log = Log("netdb")

def hashpath(name):
    assert isinstance(name, unicode), "must pass unicode object to hashpath"    
    name = name.replace(" ", "_")
    m=md5.new()
    m.update(name.encode('utf8'))
    d = m.hexdigest()
    return "/".join([d[0], d[:2], name])

class ImageDB(object):
    def __init__(self, baseurl, basedir):
        """
        @param baseurl: base URL or tuple containing several base URLs
        @type baseurl: str or (str,)
        """
        
        self.baseurl = baseurl
        self.basedir = basedir
        
    def _transform_name(self, name):
        name = name[0].upper() + name[1:]
        return name.replace(' ', '_').encode('utf8')

    def getDiskPath(self, name, width=None):
        p = self.getPath(name, width=width)
        if p:
            p = os.path.join(self.basedir, p)
        return p

    def getPath(self, name, width=None):
        if not name:
            return None
        name = name[:1].upper()+name[1:]
        
        hp = hashpath(name)
        print "HP:", hp

        p = os.path.join(self.basedir, hp)
        if os.path.exists(p):
            d = open(p).read()
        elif isinstance(self.baseurl, basestring):
            d = self._fetchURL(self.baseurl, hp)
        else: 
            for bu in self.baseurl:
                d = self._fetchURL(bu, hp)
                if d is not None:
                    break

        if d is None:
            return
        
        dest = os.path.join(self.basedir, hp)
        dn = os.path.dirname(dest)
        if not os.path.exists(dn):
            os.makedirs(dn)
        open(dest, 'wb').write(d)
        return hp

    def _fetchURL(self, baseurl, hp):
        url = "%s/%s" % (baseurl, urllib.quote(hp.encode('utf-8')))
        log.info("fetching %r" % (url,))

        opener = urllib2.build_opener()
        opener.addheaders = [('User-agent', 'PediaPress.com')]
        try:
            d = opener.open(url).read()
        except urllib2.HTTPError, err:
            if err.code == 404:
                log.error("404 - while fetching %r" % (url,))
                print '404'
                return
            raise
        return d
        
        
    
        
                 
class NetDB(object):
    def __init__(self, pagename, imagedescription=None):
        self.pagename = pagename.replace("%", "%%").replace("@TITLE@", "%(NAME)s")
        
        if imagedescription is None:
            self.imagedescription = pagename.replace("%", "%%").replace("@TITLE@", "Image:%(NAME)s")
        else:
            self.imagedescription = imagedescription.replace("%", "%%").replace("@TITLE@", "%(NAME)s")
            
        
        #self.pagename = "http://mw/index.php?title=%(NAME)s&action=raw"
        #self.imagedescription = "http://mw/index.php?title=Image:%(NAME)s&action=raw"
        
        self.pages = {}
        
    def _getpage(self, url):
        try:
            return self.pages[url]
        except KeyError:
            pass
        
        stime=time.time()
        d=urllib.urlopen(url).read()
        log.info('fetched %r in %ss' % (url,time.time()-stime))

        self.pages[url] = d
        return d
        
        
    def _dummy(self, *args, **kwargs):
        pass
    
    startCache = _dummy

    def getURL(self, title):        
        NAME = urllib.quote(title.replace(" ", "_").encode('utf8'))
        return self.pagename % dict(NAME=NAME)
    
    def title2db(self, title):
        assert isinstance(title, unicode), 'title must be of type unicode'
        return title.encode('utf-8')

    def db2title(self, dbtitle):
        assert isinstance(dbtitle, str), 'dbtitle must be of type str'
        return unicode(dbtitle, 'utf-8')

    def getImageDescription(self, title):
        NAME = urllib.quote(title.replace(" ", "_").encode('utf8'))
        url = self.imagedescription % dict(NAME=NAME)
        return self._getpage(url)

    def getImageMetaInfos(self, imgname):
        return {}

    def getTemplate(self, name, followRedirects=False):
        return self.getRawArticle(u'Template:%s' % name)

    def getRawArticle(self, title):
        r = self._getpage(self.getURL(title))
        return unicode(r, 'utf8')
    
    def getRedirect(self, title):
        return u""

    def getParsedArticle(self, title):
        raw = self.getRawArticle(title)
        a = uparser.parseString(title=title, raw=raw, wikidb=self)
        return a

    def getEditors(self, title):
        return []

class Overlay(NetDB):
    def __init__(self, wikidb, templates):
        self.__dict__.update(wikidb.__dict__)
        self.overlay_templates = templates
        
    def getTemplate(self, name, followRedirects=False):
        try:
            return self.overlay_templates[name]
        except KeyError:
            pass
        
        return super(Overlay, self).getTemplate(name, followRedirects=followRedirects)
