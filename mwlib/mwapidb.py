#! /usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2008, PediaPress GmbH
# See README.txt for additional licensing information.

import os
import re
import shutil
import tempfile
import urllib
import urllib2
import urlparse

import simplejson

from mwlib import uparser, utils
from mwlib.log import Log

log = Log("mwapidb")

if urllib2.getproxies():
    log("using proxy %r" % urllib2.getproxies())

try:
    from mwlib.licenses import lower2normal
except ImportError:
    log.warn('no licenses found')
    lower2normal = {}



# ==============================================================================

fetch_cache = {}
max_cacheable_size = 1024


def fetch_url(url, ignore_errors=False):
    if url in fetch_cache:
        return fetch_cache[url]
    
    log.info("fetching %r" % (url,))
    opener = urllib2.build_opener()
    opener.addheaders = [('User-agent', 'mwlib')]
    try:
        data = opener.open(url).read()
    except urllib2.URLError, err:
        if ignore_errors:
            log.error("%s - while fetching %r" % (err, url))
            return None
        raise RuntimeError('Could not fetch %r: %s' % (url, err))
    log.info("got %r (%d Bytes)" % (url, len(data)))
    
    if len(data) < max_cacheable_size:
        fetch_cache[url] = data
    
    return data

# ==============================================================================

articleurl_rex = re.compile(r'^(?P<scheme_host_port>https?://[^/]+)(?P<path>.*)$')
api_helper_cache = {}

def get_api_helper(url):
    """Return APIHelper instance given (e.g. article) URL.
    
    @param url: URL of a MediaWiki article
    @type url: str
    
    @returns: APIHelper instance or None if it couldn't be guessed
    @rtype: @{APIHelper}
    """
    
    mo = articleurl_rex.match(url)
    if mo is None:
        return None
    
    scheme_host_port = mo.group('scheme_host_port')
    if scheme_host_port in api_helper_cache:
        return api_helper_cache[scheme_host_port]
    
    for path in ('/w/', '/wiki/', '/'):
        base_url = scheme_host_port + path
        api_helper = APIHelper(base_url)
        if api_helper.is_usable():
            api_helper_cache[scheme_host_port] = api_helper
            return api_helper
    
    return None

# ==============================================================================


class APIHelper(object):
    def __init__(self, base_url):
        """
        @param base_url: base URL (or list of URLs) of a MediaWiki,
            i.e. URL path to php scripts,
            e.g. 'http://en.wikipedia.org/w/' for English Wikipedia.
        @type base_url: basestring or [basestring]
        """
        
        if isinstance(base_url, unicode):
            self.base_url = base_url.encode('utf-8')
        else:
            self.base_url = base_url
        if self.base_url[-1] != '/':
            self.base_url += '/'
        self.query_cache = {}
    
    def is_usable(self):
        result = self.query(meta='siteinfo', ignore_errors=True)
        if result and 'general' in result:
            return True
        return False
    
    def query(self, ignore_errors=False, **kwargs):
        args = {
            'action': 'query',
            'format': 'json',
        }
        args.update(**kwargs)
        for k, v in args.items():
            if isinstance(v, unicode):
                args[k] = v.encode('utf-8')
        q = urllib.urlencode(args)
        q = q.replace('%3A', ':') # fix for wrong quoting of url for images
        q = q.replace('%7C', '|') # fix for wrong quoting of API queries (relevant for redirects)
        data = fetch_url('%sapi.php?%s' % (self.base_url, q), ignore_errors=ignore_errors)
        if ignore_errors and data is None:
            return None
        try:
            return simplejson.loads(unicode(data, 'utf-8'))['query']
        except KeyError:
            return None
        except:
            if ignore_errors:
                return None
            raise RuntimeError('api.php query failed. Are you sure you specified the correct baseurl?')
    
    def page_query(self, **kwargs):
        q = self.query(**kwargs)
        if q is None:
            return None
        try:
            page = q['pages'].values()[0]
        except (KeyError, IndexError):
            return None
        return page
    

# ==============================================================================


class ImageDB(object):
    def __init__(self, base_url):
        """
        @param base_url: base URL of a MediaWiki,
            e.g. 'http://en.wikipedia.org/w/'
        @type base_url: basestring
        """
        
        self.api_helper = get_api_helper(base_url)
        assert self.api_helper is not None, 'invalid base URL %r' % base_url
        self.tmpdir = tempfile.mkdtemp()
    
    def clear(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
    
    def getDescriptionURL(self, name):
        """Return URL of image description page for image with given name
        
        @param name: image name (w/out namespace, i.e. w/out 'Image:')
        @type name: unicode
        
        @returns: URL to image description page
        @rtype: str
        """
    
        assert isinstance(name, unicode), 'name must be of type unicode'
        
        result = self.api_helper.page_query(titles='Image:%s' % name, prop='imageinfo', iiprop='url')
        if result is None:
            return None
        
        try:
            imageinfo = result['imageinfo'][0]
            url = imageinfo['descriptionurl']
            if url: # url can be False
                if url.startswith('/'):
                    url = urlparse.urljoin(self.api_helper.base_url, url)
                return url
            return None
        except (KeyError, IndexError):
            return None
    
    def getURL(self, name, size=None):
        """Return image URL for image with given name
        
        @param name: image name (without namespace, i.e. without 'Image:')
        @type name: unicode
        
        @returns: URL to original image
        @rtype: str
        """
        
        assert isinstance(name, unicode), 'name must be of type unicode'
        
        if size is None:
            result = self.api_helper.page_query(titles='Image:%s' % name, prop='imageinfo', iiprop='url')
        else:
            result = self.api_helper.page_query(titles='Image:%s' % name, prop='imageinfo', iiprop='url', iiurlwidth=str(size))
        if result is None:
            return None
        
        try:
            imageinfo = result['imageinfo'][0]
            if size is not None and 'thumburl' in imageinfo:
                url = imageinfo['thumburl']
            else:
                url = imageinfo['url']
            if url: # url can be False
                if url.startswith('/'):
                    url = urlparse.urljoin(self.api_helper.base_url, url)
                return url
            return None
        except (KeyError, IndexError):
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
        
        data = fetch_url(url, ignore_errors=True)
        if not data:
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
    
    def getLicense(self, name):
        """Return license of image as stated on image description page
        
        @param name: image name without namespace (e.g. without "Image:")
        @type name: unicode
        
        @returns: license of image of None, if no valid license could be found
        @rtype: unicode
        """
        
        assert isinstance(name, unicode), 'name must be of type unicode'
        
        desc_url = self.getDescriptionURL(name)
        if desc_url is None:
            return None
        
        api_helper = get_api_helper(desc_url)
        if api_helper is None:
            return None
        
        result = api_helper.page_query(titles='Image:%s' % name, prop='templates')
        if not result or 'templates' not in result:
            return None
        
        try:
            templates = [t['title'] for t in result['templates']]
        except KeyError:
            return None
        
        for t in templates:
            try:
                return lower2normal[t.split(':', 1)[-1].lower()]
            except KeyError:
                pass
        
        return None
    

# ==============================================================================

    
class WikiDB(object):
    print_template = u'Template:Print%s' # set this to none to deacticate # FIXME
    
    ip_rex = re.compile(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$')
    bot_rex = re.compile(r'\bbot\b', re.IGNORECASE)
    
    def __init__(self, base_url, license, template_blacklist=None):
        """
        @param base_url: base URL of a MediaWiki,
            e.g. 'http://en.wikipedia.org/w/'
        @type base_url: basestring
        
        @param license: title of an article containing full license text
        @type license: unicode
        
        @param template_blacklist: title of an article containing blacklisted
            templates (optional)
        @type template_blacklist: unicode
        """
        
        self.base_url = base_url
        self.license = license
        self.api_helper = get_api_helper(self.base_url)
        assert self.api_helper is not None, 'invalid base URL %r' % self.base_url
        self.template_cache = {}
        self.template_blacklist = []
        if template_blacklist is not None:
            raw = self.getRawArticle(template_blacklist)
            if raw is None:
                log.error('Could not get template blacklist article %r' % template_blacklist)
            else:
                self.template_blacklist = [template.lower().strip() 
                                           for template in re.findall('\* *\[\[.*?:(.*?)\]\]', raw)]
    
    def getURL(self, title, revision=None):
        name = urllib.quote(title.replace(" ", "_").encode('utf-8'))
        if revision is None:
            return '%sindex.php?title=%s' % (self.base_url, name)
        else:
            return '%sindex.php?title=%s&oldid=%s' % (self.base_url, name, revision)
    
    def getAuthors(self, title, revision=None, max_num_authors=10):
        """Return at most max_num_authors names of non-bot, non-anon users for
        non-minor changes of given article (before given revsion).
        
        @returns: list of principal authors
        @rtype: [unicode]
        """
        
        result = self.api_helper.page_query(
            titles=title,
            redirects=1,
            prop='revisions',
            rvprop='user|ids|flags|comment',
            rvlimit=500,
        )
        if result is None:
            return None
        
        try:
            revs = result['revisions']
        except KeyError:
            return None

        if revision is not None:
            revision = int(revision)
            revs = [r for r in revs if r['revid'] < revision]
        
        authors = [r['user'] for r in revs
                   if not r.get('anon')
                   and not self.ip_rex.match(r['user'])
                   and not r.get('minor')
                   and not self.bot_rex.search(r.get('comment', ''))
                   and not self.bot_rex.search(r['user'])
                   ]
        author2count = {}
        for a in authors:
            try:
                author2count[a] += 1
            except KeyError:
                author2count[a] = 1
        author2count = author2count.items()
        author2count.sort(key=lambda a: -a[1])
        return [a[0] for a in author2count[:max_num_authors]]
    
    def getTemplate(self, name, followRedirects=True):
        """
        Note: *Not* following redirects is unsupported!
        """
        
        try:
            return self.template_cache[name]
        except KeyError:
            pass
        
        if ":" in name:
            name = name.split(':', 1)[1]
        
        if name.lower() in self.template_blacklist:
            log.info("ignoring blacklisted template:" , repr(name))
            return None
        
        titles = ['Template:%s' % name]
        if self.print_template:
            titles.append(self.print_template % name)
        for title in titles:
            log.info("Trying template %r" % (title,))
            c = self.getRawArticle(title)
            if c is not None:
                self.template_cache[name] = c
                return c
        
        return None
    
    def getRawArticle(self, title, revision=None):
        if not title:
            return None
        
        if revision is None:
            page = self.api_helper.page_query(titles=title, redirects=1, prop='revisions', rvprop='content')
        else:
            page = self.api_helper.page_query(revids=revision, prop='revisions', rvprop='content')
            if page['title'] != title: # given revision could point to another article!
                return None
        if page is None:
            return None
        try:
            return page['revisions'][0].values()[0]
        except KeyError:
            return None
    
    def getMetaData(self):
        result = self.api_helper.query(meta='siteinfo')
        try:
            g = result['general']
            result = {
                'url': g['base'],
                'name': '%s (%s)' % (g['sitename'], g['lang']),
            }
            if self.license is None:
                log.warn('No license given')
            else: 
                wikitext = self.getRawArticle(self.license)
                assert wikitext is not None, 'Could not get license article %r' % self.license
                result['license'] = {
                    'name': g['rights'],
                    'wikitext': wikitext,
                }
            return result
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
    
