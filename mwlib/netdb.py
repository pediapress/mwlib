#! /usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2008, PediaPress GmbH
# See README.txt for additional licensing information.

# An alternative solution to construct the hashpath of images would be to use
# api.php, e.g.
# fetch the page http://de.wikipedia.org/w/api.php?action=query&titles=Bild:SomePic.jpg&prop=imageinfo&iiprop=url&format=json

import os
import sys
import urllib
import urllib2
try:
    from hashlib import md5
except ImportError:
    from md5 import md5
import shutil
import sys
import time
import tempfile
import re

from mwlib import uparser, utils
from mwlib.log import Log

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
    d = md5(name.encode('utf-8')).hexdigest()
    return "/".join([d[0], d[:2], name])

class ImageDB(object):
    convert_command = 'convert' # name of/path to ImageMagick's convert tool
    
    def __init__(self, baseurl, cachedir=None, wikidb=None, knownLicenses=None):
        """Init ImageDB with a base URL (or a list of base URLs) and optionally
        with a cache directory.
        
        @param baseurl: base URL or sequence containing several base URLs
        @type baseurl: unicode or (unicode,)
        
        @param cachedir: image cache directory (optional)
        @type cachedir: basestring or None
        
        @param wikidb: WikiDB instance used to fetch image description pages to
            find out image licenses
        @type wikidb: object
        
        @param knownLicenses: list of known license templates (whose name is the
            name of the license) which may appear on image description pages
        @type knownLicenses: [unicode]
        """
        
        if isinstance(baseurl, unicode):
            self.baseurls = [baseurl.encode('ascii')]
        else:
            self.baseurls = []
            for bu in baseurl:
                if isinstance(bu, unicode):
                    bu = bu.encode('ascii')
                self.baseurls.append(bu)
        
        if cachedir:
            self.cachedir = cachedir
            self.tempcache = False
        else:
            self.cachedir = tempfile.mkdtemp()
            self.tempcache = True
        if self.cachedir[-1] != '/':
            self.cachedir += '/' # needed for getPath() to work correctly
        
        self.wikidb = wikidb

        oredLicenses = '|'.join(['(%s)' % re.escape(license)
                                 for license in (knownLicenses or [])])
        self.licenseRegexp = re.compile(r'{{(?P<license>%s)}}' % oredLicenses)
        
        self.name2license = {}
    
    def clear(self):
        """Delete temporary cache directory (i.e. only if no cachedir has been
        passed to __init__().
        """
        
        if self.tempcache:
            shutil.rmtree(self.cachedir)
    
    def getURL(self, name, size=None):
        """Return image URL for image with given name
        
        @param name: image name (without namespace, i.e. without 'Image:')
        @type name: unicode
        
        @returns: URL to original image
        @rtype: str
        """
        
        assert isinstance(name, unicode), 'name must be of type unicode'
        
        # use getDiskPath() to fetch and cache (!) image
        path = self.getDiskPath(name, size=size)
        if path is None:
            return None
        
        # first, look for a cached image with that name (in any size)
        for baseurl in self.baseurls:
            urldir = self._getCacheDirForBaseURL(baseurl)
            if not path.startswith(urldir):
                continue
            return self._getImageURLForBaseURL(baseurl, name)
    
    def getPath(self, name, size=None):
        """Return path to image with given parameters relative to cachedir"""
        
        path = self.getDiskPath(name, size=size)
        if path is None:
            return None
        assert path.startswith(self.cachedir), 'invalid path from getDiskPath()'
        return path[len(self.cachedir):]
    
    def getDiskPath(self, name, size=None):
        """Return filename for image with given name. If the image is not found
        in the cache, it is fetched per HTTP and converted.
        
        @param name: image name (without namespace, i.e. without 'Image:')
        @type name: unicode
        
        @param size: if given, the image is converted to the given maximum size
            (i.e. the image is scaled so that neither its  width nor its height
            exceed size)
        @type size: int or NoneType
        
        @returns: filename of image
        @rtype: basestring
        """

        assert isinstance(name, unicode), 'name must be of type unicode'
        
        path = self._getImageFromCache(name, size=size)
        if path:
            return path
        
        tmpfile, baseurl = self._fetchImage(name)
        if tmpfile is None:
            return None
        
        self.name2license[name] = self._fetchLicense(baseurl, name)
        
        path = self._convertToCache(tmpfile, baseurl, name, size=size)
        
        try:
            os.unlink(tmpfile)
        except IOError:
            log.warn('Could not delete temp file %r' % tmpfile)
        
        return path
    
    def _fetchLicense(self, baseurl, name):
        if self.wikidb is None:
            return None
        
        raw = self.wikidb.getImageDescription(name,
            urlIndex=self.baseurls.index(baseurl),
        )
        if raw is None:
            return None
        
        mo = re.search(self.licenseRegexp, raw)
        if mo is None:
            return None
        
        return mo.group('license')
    
    def getLicense(self, name):
        """Return license of image as stated on image description page
        
        @param name: image name without namespace (e.g. without "Image:")
        @type name: unicode
        
        @returns: license of image of None, if no valid license could be found
        @rtype: str
        """
        
        assert isinstance(name, unicode), 'name must be of type unicode'
        return self.name2license.get(name)
    
    def _getImageFromCache(self, name, size=None):
        """Look in cachedir for an image with the given parameters"""
        
        for baseurl in self.baseurls:
            path = self._getCachedImagePath(baseurl, name, size=size)
            if path is not None and os.path.exists(path):
                return path
        return None
    
    def _getCacheDirForBaseURL(self, baseurl):
        """Construct the path of the cache directory for the given base URL.
        This directory doesn't need to exist.
        """
        
        return os.path.join(self.cachedir,
                            md5(baseurl.encode('utf-8')).hexdigest()[:8])
    
    def _getCachedImagePath(self, baseurl, name, size=None, makedirs=False):
        """Construct a filename for an image with the given parameters inside
        the cache directory. The file doesn't need to exist. If makedirs is True
        create all directories up to filename.
        """
        
        urlpart = self._getCacheDirForBaseURL(baseurl)
        if size is not None:
            sizepart = '%dpx' % size
        else:
            sizepart = 'orig'
        
        if name.lower().endswith('.svg'):
            if size is None:
                log.warn('Cannot get SVG image when no size is given')
                return None
            name += '.png'
        if name.lower().endswith('.gif'):
            name += '.png'
        name = (name[0].upper() + name[1:]).replace(' ', '_').replace("'", "-")
        
        d = os.path.join(urlpart, sizepart)
        if makedirs and not os.path.isdir(d):
            os.makedirs(d)
        return os.path.join(d, utils.fsescape(name))
    
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
        """Convert image in file named srcfile to have the given maximum size.
        Save the converted image in the cache directory for the given baseurl.
        
        @returns: filename of converted image
        @rtype: basestring
        """
        destfile = self._getCachedImagePath(baseurl, name, size=size, makedirs=True)
        if size is not None:
            thumbnail = '-thumbnail "%dx%d>"' % (size, size)
        else:
            thumbnail = '-strip'
            
        opts = '-background white -density 100 -flatten -coalesce %(thumbnail)s' % {
            'thumbnail': thumbnail,
        }
        cmd = "%(convert)s %(opts)s '%(src)s[0]' '%(dest)s'" % {
            'convert': self.convert_command,
            'opts': opts,
            'src': srcfile,
            'dest': destfile,
        }
        log.info('executing %r' % cmd)
        rc = utils.shell_exec(cmd)
        if rc != 0:
            log.error('Could not convert %r: convert returned %d' % (name, rc))
            return None
        
        return destfile
    

# ==============================================================================
    
def normname(name):
    name = name.strip().replace("_", " ")
    name = name[:1].upper()+name[1:]
    return name
        
                 
class NetDB(object):
    redirect_rex = re.compile(r'^#Redirect:?\s*?\[\[(?P<redirect>.*?)\]\]', re.IGNORECASE)

    def __init__(self, pagename,
        imagedescriptionurls=None,
        templateurls=None,
        templateblacklist=None,
        defaultauthors=None,
    ):
        """
        @param pagename: URL to page in wikitext format. @TITLE@ gets replaced
            with the page name and @REVISION@ gets replaced with the requested
            revision/oldid. E.g.

                "http://mw/index.php?title=@TITLE@&action=raw&oldid=@TITLE@"
        
        @type pagename: str
        
        @param imagedescriptionurls: list of URLs to image description pages in
            wikitext format. @TITLE@ gets replaced with the image title w/out
            its prefix. E.g.
            
                ["http://mw/index.php?title=Image:@TITLE@s&action=raw"]
            
            The list must be of the same length as the baseurl list of the
            accompanying ImageDB, and the URL with the corresponding position
            in the list is used to retrieve the description page.
        @type imagedescriptionurls: [str]
        
        @param templateurls: list of URLs to template pages in wikitext format.
            @TITLE@ gets replaced with the template title. E.g.
            
                ["http://mw/index.php?title=Template:@TITLE@s&action=raw"]
            
            If more than one URL is specified, URLs are tried in given order.
        @type templateurls: [str]
        
        @param defaultauthors: list of default (principal) authors for articles
        @type defaultauthors: [unicode]
        """
        
        self.pagename = pagename.replace("%", "%%").replace("@TITLE@", "%(NAME)s").replace("@REVISION@", "%(REVISION)s")
        
        if templateurls is None:
            templateurls = []
        self.templateurls = [x.replace("%", "%%").replace("@TITLE@", "%(NAME)s")
                             for x in templateurls]
        
        if imagedescriptionurls is None:
            imagedescriptionurls = []
        self.imagedescriptionurls = [x.replace("%", "%%").replace("@TITLE@", "%(NAME)s")
                                     for x in imagedescriptionurls]
        
        if templateblacklist:
            self.templateblacklist = self._readTemplateBlacklist(templateblacklist)
        else:
            self.templateblacklist = []
        
        if defaultauthors:
            self.defaultauthors = defaultauthors
        else:
            self.defaultauthors = []
        
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
    
    def getAuthors(self, title, revision=None):
        return list(self.defaultauthors)
    
    def title2db(self, title):
        assert isinstance(title, unicode), 'title must be of type unicode'
        return title.encode('utf-8')

    def db2title(self, dbtitle):
        assert isinstance(dbtitle, str), 'dbtitle must be of type str'
        return unicode(dbtitle, 'utf-8')

    def getImageDescription(self, title, urlIndex=0):
        """Fetch the image description page for the image with the given title.
        If baseurl and self.imagedescriptions contains more than one URL, use
        the one which starts with baseurl.
        
        @param title: title of the image w/out prefix (like Image:)
        @type title: unicode
        
        @param urlIndex: index for imagedescriptionurls
        @type urlIndex: int
        
        @returns: wikitext of image description page or None
        @rtype: unicode or None
        """
        
        if not self.imagedescriptionurls:
            return None
        
        raw = self._getpage(self.imagedescriptionurls[urlIndex] % {
            'NAME': urllib.quote(title.replace(" ", "_").encode('utf8')),
        })
        if raw is None:
            return None
        
        return unicode(raw, 'utf-8')
    
    def getTemplate(self, name, followRedirects=False):
        if ":" in name:
            name = name.split(':', 1)[1]

        
        if name.lower() in self.templateblacklist:
            log.info("ignoring blacklisted template:" , repr(name))
            return None
        name = urllib.quote(name.replace(" ", "_").encode('utf8'))
        for u in self.templateurls:
            url = u % dict(NAME=name)
            log.info("Trying %r" %(url,))
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

    def getParsedArticle(self, title, revision=None):
        raw = self.getRawArticle(title, revision=revision)
        if raw is None:
            return None
        a = uparser.parseString(title=title, raw=raw, wikidb=self)
        return a


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
    
