#! /usr/bin/env python

# Copyright (c) 2008, PediaPress GmbH
# See README.txt for additional licensing information.

## http://mw/index.php?title=Image:Bla.jpg&action=raw
## http://mw/index.php?title=Template:MYHEADER&action=raw


import os
import sys
import urllib
import urllib2
import md5
import shutil
import sys
import time
import tempfile
import re

from mwlib import uparser
from mwlib.log import Log
from mwlib.utils import shell_exec

log = Log("netdb")

# ==============================================================================

def hashpath(name):
    """Compute hashpath for an image in the same way as MediaWiki does
    
    @param name: name of an image
    @type name: unicode
    
    @returns: hashpath to image
    @type: str
    """
    
    name = name.replace(' ', '_')
    name = name[:1].upper()+name[1:]
    d = md5.new(name.encode('utf-8')).hexdigest()
    return "/".join([d[0], d[:2], name])

class ImageDB(object):
    convert_command = 'convert' # name of/path to ImageMagick's convert tool
    
    def __init__(self, baseurl, cachedir=None):
        """Init ImageDB with a base URL (or a list of base URLs) and optionally
        with a cache directory.
        
        @param baseurl: base URL or sequence containing several base URLs
        @type baseurl: unicode or (unicode,)
        
        @param cachedir: image cache directory (optional)
        @type cachedir: basestring or None
        """
        
        if isinstance(baseurl, unicode):
            baseurl = (baseurl.encode('ascii'),)
        elif isinstance(baseurl, tuple):
            baseurl = tuple([bu.encode('ascii') for bu in baseurl if isinstance(bu, unicode)])
        self.baseurls = baseurl
        
        if cachedir:
            self.cachedir = cachedir
            self.tempcache = False
        else:
            self.cachedir = tempfile.mkdtemp()
            self.tempcache = True
        if self.cachedir[-1] != '/':
            self.cachedir += '/' # needed for getPath() to work correctly
    
    def clear(self):
        """Delete temporary cache directory (i.e. only if no cachedir has been
        passed to __init__().
        """
        
        if self.tempcache:
            shutil.rmtree(self.cachedir)
    
    def getURL(self, name, size=None, grayscale=False):
        """Return image URL for image with given name
        
        @param name: image name (without namespace, i.e. without 'Image:')
        @type name: unicode
        
        @returns: URL to original image
        @rtype: str
        """
        
        assert isinstance(name, unicode), 'name must be of type unicode'
        
        # use getDiskPath() to fetch and cache (!) image
        path = self.getDiskPath(name, size=size, grayscale=grayscale)
        if path is None:
            return None
        
        # first, look for a cached image with that name (in any size)
        for baseurl in self.baseurls:
            urldir = self._getCacheDirForBaseURL(baseurl)
            if not path.startswith(urldir):
                continue
            return self._getImageURLForBaseURL(baseurl, name)
    
    def getPath(self, name, size=None, grayscale=False):
        """Return path to image with given parameters relative to cachedir"""
        
        path = self.getDiskPath(name, size=size, grayscale=grayscale)
        if path is None:
            return None
        assert path.startswith(self.cachedir), 'invalid path from getDiskPath()'
        return path[len(self.cachedir):]
    
    def getDiskPath(self, name, size=None, grayscale=False):
        """Return filename for image with given name. If the image is not found
        in the cache, it is fetched per HTTP and converted.
        
        @param name: image name (without namespace, i.e. without 'Image:')
        @type name: unicode
        
        @param size: if given, the image is converted to the given maximum size
            (i.e. the image is scaled so that neither its  width nor its height
            exceed size)
        @type size: int or NoneType
        
        @param grayscale: if True, the image is converted to grayscale
        @type grayscale: bool
        
        @returns: filename of image
        @rtype: basestring
        """
        
        assert isinstance(name, unicode), 'name must be of type unicode'
        
        path = self._getImageFromCache(name, size=size, grayscale=grayscale)
        if path:
            return path
    
        tmpfile, baseurl = self._fetchImage(name)
        if tmpfile is None:
            return None
        
        colorpath, graypath = self._convertToCache(tmpfile, baseurl, name, size=size)
        
        try:
            os.unlink(tmpfile)
        except IOError:
            log.warn('Could not delete temp file %r' % tmpfile)
        
        return graypath if grayscale else colorpath
    
    def _getImageFromCache(self, name, size=None, grayscale=False):
        """Look in cachedir for an image with the given parameters"""
        
        for baseurl in self.baseurls:
            path = self._getCachedImagePath(baseurl, name, size=size, grayscale=grayscale)
            if path is not None and os.path.exists(path):
                return path
        return None
    
    def _getCacheDirForBaseURL(self, baseurl):
        """Construct the path of the cache directory for the given base URL.
        This directory doesn't need to exist.
        """
        
        return os.path.join(self.cachedir,
                            md5.new(baseurl.encode('utf-8')).hexdigest()[:8])
    
    def _getCachedImagePath(self, baseurl, name, size=None, grayscale=False, makedirs=False):
        """Construct a filename for an image with the given parameters inside
        the cache directory. The file doesn't need to exist. If makedirs is True
        create all directories up to filename.
        """
        
        urlpart = self._getCacheDirForBaseURL(baseurl)
        sizepart = '%dpx' % size if size is not None else 'orig'
        graypart = 'gray' if grayscale else 'color'
        
        if name.endswith('.svg'):
            if size is None:
                log.warn('Cannot get SVG image when no size is given')
                return None
            name += '.png'
        if name.endswith('.gif'):
            name += '.png'
        name = (name[0].upper() + name[1:]).replace(' ', '_')
        
        d = os.path.join(urlpart, sizepart, graypart)
        if makedirs and not os.path.isdir(d):
            os.makedirs(d)
        return os.path.join(d, name)
    
    def _fetchImage(self, name):
        """Fetch image with given name in original (i.e. biggest) size per HTTP.
        
        @returns: filename of written image and base URL used to retrieve the
            image or (None, None) if the image could not be fetched
        @rtype: (basestring, str) or (NoneType, NoneType)
        """
        
        for baseurl in self.baseurls:
            path = self._fetchImageFromBaseURL(baseurl, name)
            if path:
                return path, baseurl
        return None, None
    
    def _getImageURLForBaseURL(self, baseurl, name):
        """Construct a URL for the image with given name under given base URL"""
        
        hp = hashpath(name).encode('utf-8')
        return urllib.basejoin(baseurl, urllib.quote(hp))
    
    def _fetchImageFromBaseURL(self, baseurl, name):
        """Fetch image with given name under given baseurl and write it to a
        tempfile.
        
        @returns: filename of written image or None if image could not be fetched
        @rtype: basestring or NoneType
        """
        
        url = self._getImageURLForBaseURL(baseurl, name)
        log.info("fetching %r" % (url,))
        opener = urllib2.build_opener()
        opener.addheaders = [('User-agent', 'mwlib')]
        try:
            data = opener.open(url).read()
            log.info("got image: %r" % url)
            fd, filename = tempfile.mkstemp()
            os.write(fd, data)
            os.close(fd)
            return filename
        except urllib2.URLError, err:
            log.error("%s - while fetching %r" % (err, url))
            return None
    
    def _convertToCache(self, srcfile, baseurl, name, size=None):
        """Convert image in file named srcfile to have the given maximum size
        and additionally convert it to grayscale. Save the converted image in
        the cache directory for the given baseurl.
        
        @returns: filenames of color and grayscale version of converted image
        @rtype: (basestring, basestring)
        """
        
        colorpath = self._getCachedImagePath(baseurl, name, size=size, grayscale=False, makedirs=True)
        opts = '-background white -coalesce -density 100 -flatten %(resize)s' % {
            'resize': '-resize %dx%d' % (size, size) if size is not None else '',
        }
        cmd = "%(convert)s %(opts)s '%(src)s[0]' '%(dest)s'" % {
            'convert': self.convert_command,
            'opts': opts,
            'src': srcfile,
            'dest': colorpath,
        }
        log.info('executing %r' % cmd)
        rc = shell_exec(cmd)
        if rc != 0:
            log.error('Could not convert %r: convert returned %d' % (name, rc))
            return None, None
        
        graypath = self._getCachedImagePath(baseurl, name, size=size, grayscale=True, makedirs=True)
        cmd = '%(convert)s -type GrayScale "%(src)s" "%(dest)s"' % {
            'convert': self.convert_command,
            'src': colorpath,
            'dest': graypath,
        }
        log.info('executing %r' % cmd)
        rc = shell_exec(cmd)
        if rc != 0:
            log.error('Could not convert %r to grayscale: convert returned %d' % (name, rc))
            graypath = None
        
        return colorpath, graypath
    

# ==============================================================================
    
def normname(name):
    name = name.strip().replace("_", " ")
    name = name[:1].upper()+name[1:]
    return name
        
                 
class NetDB(object):
    redirect_rex = re.compile(r'^#Redirect:?\s*?\[\[(?P<redirect>.*?)\]\]', re.IGNORECASE)

    def __init__(self, pagename, imagedescription=None, templateurls=None, templateblacklist=None):
        self.pagename = pagename.replace("%", "%%").replace("@TITLE@", "%(NAME)s").replace("@REVISION@", "%(REVISION)s")

        self.templateurls = [x.replace("%", "%%").replace("@TITLE@", "%(NAME)s") for x in templateurls]

        if imagedescription is None:
            self.imagedescription = pagename.replace("%", "%%").replace("@TITLE@", "Image:%(NAME)s")
        else:
            self.imagedescription = imagedescription.replace("%", "%%").replace("@TITLE@", "%(NAME)s")
            
        if templateblacklist:
            self.templateblacklist = self._readTemplateBlacklist(templateblacklist)
        else:
            self.templateblacklist = []

        #self.pagename = "http://mw/index.php?title=%(NAME)s&action=raw&oldid=%(REVISION)s"
        #self.imagedescription = "http://mw/index.php?title=Image:%(NAME)s&action=raw"
        
        self.pages = {}
        
    def _getpage(self, url, expectedContentType='text/x-wiki'):
        try:
            return self.pages[url]
        except KeyError:
            pass
        
        stime=time.time()
        response = urllib.urlopen(url)
        data = response.read()
        log.info('fetched %r in %ss' % (url, time.time()-stime))

        if expectedContentType:
            ct = response.info().gettype()
            if ct != expectedContentType:
                log.warn('Skipping page %r with content-type %r (%r was expected). Skipping.'\
                        % (url, ct, expectedContentType))
                return None
        
        self.pages[url] = data
        return data

    def _readTemplateBlacklist(self,templateblacklist):
        if not templateblacklist:
            return []
        try:
            content = urllib.urlopen(templateblacklist).read()
            return [template.lower().strip() for template in re.findall('\* *\[\[.*?:(.*?)\]\]', content)]
        except: # fixme: more sensible error handling...
            log.error('Error fetching template blacklist from url:', templateblacklist)
            return []
        
    def _dummy(self, *args, **kwargs):
        pass
    
    startCache = _dummy

    def getURL(self, title, revision=None):        
        name = urllib.quote(title.replace(" ", "_").encode('utf8'))
        if revision is None:
            return self.pagename % dict(NAME=name, REVISION='0')
        else:
            return self.pagename % dict(NAME=name, REVISION=revision)
    
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
        if ":" in name:
            name = name.split(':', 1)[1]

        
        if name.lower() in self.templateblacklist:
            log.info("ignoring blacklisted template:" , repr(name))
            return None
        name = urllib.quote(name.replace(" ", "_").encode('utf8'))
        for u in self.templateurls:
            url = u % dict(NAME=name)
            print "Trying", url
            c=self._getpage(url)
            if c:
                log.info("got content from", url)
                res=unicode(c, 'utf8')
                mo = self.redirect_rex.search(res)
                if mo:
                    redirect = mo.group('redirect')
                    redirect = normname(redirect.split("|", 1)[0].split("#", 1)[0])
                    return self.getTemplate(redirect)
                return res




        #return self.getRawArticle(u'Template:%s' % name)

    def getRawArticle(self, title, revision=None):
        r = self._getpage(self.getURL(title, revision=revision))
        if r is None:
            return None
        return unicode(r, 'utf8')
    
    def getRedirect(self, title):
        return u""

    def getParsedArticle(self, title):
        raw = self.getRawArticle(title)
        if raw is None:
            return None
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
    
