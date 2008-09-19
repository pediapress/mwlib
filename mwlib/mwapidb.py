#! /usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2008, PediaPress GmbH
# See README.txt for additional licensing information.

import cgi
import cookielib
import os
import re
import shutil
import tempfile
import time
import urllib
import urllib2
import urlparse

import simplejson

from mwlib import utils, metabook, wikidbbase, uparser, parser
from mwlib.log import Log

log = Log("mwapidb")

# ==============================================================================

class MWAPIError(RuntimeError):
    """MediaWiki API error"""

# ==============================================================================

articleurl_rex = re.compile(r'^(?P<scheme_host_port>https?://[^/]+)(?P<path>.*)$')
api_helper_cache = {}

def get_api_helper(url):
    """Return APIHelper instance for given (e.g. article) URL.
    
    @param url: URL of a MediaWiki article
    @type url: str
    
    @returns: APIHelper instance or None if it couldn't be guessed
    @rtype: @{APIHelper}
    """
    
    try:
        scheme, netloc, path, params, query, fragment = urlparse.urlparse(url)
    except ValueError:
        return None
    if not (scheme and netloc):
        return None
    
    if '/wiki/' in path:
        path_prefix = path[:path.find('/wiki/')]
    elif '/w/' in path:
        path_prefix = path[:path.find('/w/')]
    else:
        path_prefix = ''
    
    prefix = '%s://%s%s' % (scheme, netloc, path_prefix)
    try:
        return api_helper_cache[prefix]
    except KeyError:
        pass

    for path in ('/w/', '/wiki/', '/'):
        base_url = '%s%s' % (prefix, path)
        api_helper = APIHelper(base_url)
        if api_helper.is_usable():
            api_helper_cache[prefix] = api_helper
            return api_helper
    
    return None


# ==============================================================================

def parse_article_url(url, title_encoding='utf-8'):
    """Return APIHelper instance, title and revision for given article URL.
    Return None if the information could not be guessed.
    
    @param url: article URL
    @type url: str
    
    @param title_encoding: encoding of URL
    @type title_encoding: str
    
    @returns: None or dict containing 'api_helper', 'title' and 'revision'
    @rtype: {str: object} or NoneType
    """
    
    scheme, netloc, path, params, query, fragment = urlparse.urlparse(url)
    if scheme is None or netloc is None or path is None:
        return None
    args = cgi.parse_qs(query)
    
    # example: http://some.host/bla/index.php?title=Article_title&oldid=1234
    if path.endswith('index.php'):
        if 'title' not in args or not args['title']:
            return None
        base_url = url[:url.find('index.php')]
        title = unicode(args['title'][0], title_encoding, 'ignore').replace('_', ' ')
        revision = None
        try:
            revision = int(args['oldid'][0])
        except (KeyError, ValueError):
            pass
        api_helper = APIHelper(base_url)
        if not api_helper.is_usable():
            return None
        return {
            'api_helper': api_helper,
            'title': title,
            'revision': revision,
        }
    
    api_helper = get_api_helper(url)
    if api_helper is None:
        return None

    for part in ('index.php/', '/wiki/'):
        if part in path:
            return {
                'api_helper': api_helper,
                'title': unicode(
                    path[path.find(part) + len(part):],
                    title_encoding,
                    'ignore'
                ).replace('_', ' '),
                'revision': None,
            }
    
    return {
        'api_helper': api_helper,
        'title': unicode(path.rsplit('/', 1)[-1], title_encoding, 'ignore').replace('_', ' '),
        'revision': None,
    }


# ==============================================================================


class APIHelper(object):
    """
    @ivar long_request: log a warning if an HTTP requests lasts longer than this
       time (in seconds)
    @type lon_request: float or int
    """
    long_request = 2
    
    def __init__(self, base_url, script_extension=None):
        """
        @param base_url: base URL of a MediaWiki, i.e. URL path to php scripts,
            e.g. 'http://en.wikipedia.org/w/' for English Wikipedia.
        @type base_url: basestring
        
        @param script_extension: script extension for PHP scripts
        @type script_extension: basestring
        """
        
        if isinstance(base_url, unicode):
            self.base_url = base_url.encode('utf-8')
        else:
            self.base_url = base_url
        if self.base_url[-1] != '/':
            self.base_url += '/'
        if not script_extension:
            self.script_extension = '.php'
        else:
            self.script_extension = script_extension        
        if isinstance(self.script_extension, unicode):
            self.script_extension = self.script_extension.encode('utf-8')
        if self.script_extension[0] != '.':
            self.script_extension = '.' + self.script_extension
        self.query_cache = {}
        self.opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookielib.CookieJar()))
        self.opener.addheaders = [('User-agent', 'mwlib')]
    
    def is_usable(self):
        result = self.query(meta='siteinfo', ignore_errors=True)
        if result and 'general' in result:
            return True
        return False
    
    def login(self, username, password, domain=None):
        """Login via MediaWiki API
        
        @param username: username
        @type username: unicode
        
        @param password: password
        @type password: unicode
        
        @param domain: optional domain
        @type domain: unicode
        
        @returns: True if login succeeded, False otherwise
        @rtype: bool
        """
        
        args = {
            'action': 'login',
            'lgname': username.encode('utf-8'),
            'lgpassword': password.encode('utf-8'),
            'format': 'json',
        }
        if domain is not None:
            args['lgdomain'] = domain.encode('utf-8')
        result = utils.fetch_url('%sapi%s' % (self.base_url, self.script_extension),
            post_data=args,
            ignore_errors=False,
            opener=self.opener,
        )
        result = simplejson.loads(result)
        if 'login' in result and result['login'].get('result') == 'Success':
            return True
        return False
    
    def query(self, ignore_errors=True, num_tries=2, **kwargs):
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
        
        for i in range(num_tries):
            try:
                s = time.time()
                data = utils.fetch_url('%sapi%s?%s' % (self.base_url, self.script_extension, q),
                    ignore_errors=ignore_errors,
                    opener=self.opener,
                )
                elapsed = time.time() - s
                if elapsed > self.long_request:
                    log.warn('Long request: HTTP request took %f s' % elapsed)
                if data is not None:
                    break
            except:
                if i == num_tries - 1:
                    raise
            log.warn('Fetching failed. Trying again.')
            time.sleep(0.5)
        
        if ignore_errors and data is None:
            log.error('Got no data from api%s' % self.script_extension)
            return None
        try:
            data = unicode(data, 'utf-8')
            if data and data[0] == u'\ufeff': # strip off BOM
                # Note that a BOM is actually *not allowed* at the beginning of a JSON string
                # see http://www.ietf.org/rfc/rfc4627.txt, section "3. Encoding"
                data = data[1:]
            return simplejson.loads(data)['query']
        except KeyError:
            log.error('Response from api%s did not contain a query result' % self.script_extension)
            return None
        except Exception, e:
            log.error('Got exception: %r' % e)
            if ignore_errors:
                return None
            raise RuntimeError('api%s query failed. Are you sure you specified the correct base URL?' % self.script_extension)
    
    def page_query(self, **kwargs):
        q = self.query(**kwargs)
        if q is not None:
            try:
                return q['pages'].values()[0]
            except (KeyError, IndexError):
                return None
        return None
    

# ==============================================================================


class ImageDB(object):
    def __init__(self,
        base_url=None,
        username=None,
        password=None,
        domain=None,
        api_helper=None,
        script_extension=None,
    ):
        """
        @param base_url: base URL of a MediaWiki, e.g. 'http://en.wikipedia.org/w/'
        @type base_url: basestring
        
        @param username: username to login with (optional)
        @type username: unicode
        
        @param password: password to login with (optional)
        @type password: unicode
        
        @param domain: domain to login with (optional)
        @type domain: unicode
        
        @param api_helper: APIHelper instance
        @type api_helper: L{APIHelper}
        
        @param script_extension: script extension for PHP scripts
        @type script_extension: basestring
        """
        
        if api_helper is not None:
            assert base_url is None, 'either api_helper or base_url can be given, not both'
            self.api_helper = api_helper
        else:
            self.api_helper = APIHelper(base_url, script_extension=script_extension)
        
        if username is not None:
            if not self.login(username, password, domain=domain):
                raise MWAPIError('Login failed')
        
        if not self.api_helper.is_usable():
            raise MWAPIError('Invalid base URL: %r' % base_url)
        
        self.tmpdir = tempfile.mkdtemp()
        self.wikidb = None
    
    def clear(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
    
    def login(self, username, password, domain=None):
        return self.api_helper.login(username, password, domain=domain)
    
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
            url = imageinfo.get('descriptionurl')
            if url: # url can be False (!) or non-existant
                if url.startswith('/'):
                    url = urlparse.urljoin(self.api_helper.base_url, url)
                return url
            else:
                if self.wikidb is None:
                    self.wikidb = WikiDB(api_helper=self.api_helper)
                title = 'Image:%s' % name
                art = self.wikidb.getRawArticle(title)
                if art is not None:
                    return self.wikidb.getURL(title)
        except (KeyError, IndexError):
            pass
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

        ext = url.rsplit('.')[-1]
        if size is not None:
            ext = '%dpx.%s' % (size, ext)
        else:
            ext = '.%s' % ext
        filename = os.path.join(self.tmpdir, utils.fsescape(name + ext))    
        if utils.fetch_url(url, ignore_errors=True, output_filename=filename):
            return filename
        else:
            return None
    
    def getImageTemplates(self, name, wikidb=None):
        """Return template names used on the image description page
        
        @param name: image name without namespace (e.g. without "Image:")
        @type name: unicode
        
        @returns: list of template names
        @rtype: [unicode]
        """
        
        assert isinstance(name, unicode), 'name must be of type unicode'
        
        desc_url = self.getDescriptionURL(name)
        if desc_url is None:
            return []
        
        print desc_url
        api_helper = get_api_helper(desc_url)
        if api_helper is None:
            if wikidb is not None:
                api_helper = wikidb.api_helper
            else:
                return []
        
        result = api_helper.page_query(titles='Image:%s' % name, prop='templates')
        if not result or 'templates' not in result:
            return []
        
        try:
            return [t['title'].split(':', 1)[-1] for t in result['templates']]
        except KeyError:
            return []
    

# ==============================================================================

    
class WikiDB(wikidbbase.WikiDBBase):
    print_template = u'Template:Print%s' # set this to none to deacticate # FIXME
    
    ip_rex = re.compile(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$')
    bot_rex = re.compile(r'\bbot\b', re.IGNORECASE)
    
    def __init__(self,
        base_url=None,
        username=None,
        password=None,
        domain=None,
        template_blacklist=None,
        template_exclusion_category=None,
        api_helper=None,
        script_extension=None,
    ):
        """
        @param base_url: base URL of a MediaWiki,
            e.g. 'http://en.wikipedia.org/w/'
        @type base_url: basestring
        
        @param username: username to login with (optional)
        @type username: unicode
        
        @param password: password to login with (optional)
        @type password: unicode
        
        @param domain: domain to login with (optional)
        @type domain: unicode
        
        @param template_blacklist: title of an article containing blacklisted
            templates (optional)
        @type template_blacklist: unicode
        
        @param template_exclusion_category: title of a category for templates to
            be excluded (optional)
        @type template_exclusion_category: unicode
        
        @param api_helper: APIHelper instance
        @type api_helper: L{APIHelper}
        
        @param script_extension: script extension for PHP scripts
        @type script_extension: basestring
        """
        
        if api_helper is not None:
            assert base_url is None, 'either api_helper or base_url can be given, not both'
            self.api_helper = api_helper
        else:
            self.api_helper = APIHelper(base_url, script_extension=script_extension)
        
        if username is not None:
            if not self.login(username, password, domain=domain):
                raise MWAPIError('Login failed')
        
        if not self.api_helper.is_usable():
            raise MWAPIError('Invalid base URL: %r' % base_url)
        
        self.template_cache = {}
        self.setTemplateExclusion(
            blacklist=template_blacklist,
            category=template_exclusion_category,
        )
        self.source = None
    
    def setTemplateExclusion(self, blacklist=None, category=None):
        self.template_exclusion_category = category
        self.template_blacklist = []
        if blacklist:
            raw = self.getRawArticle(blacklist)
            if raw is None:
                log.error('Could not get template blacklist article %r' % (
                    blacklist,
                ))
            else:
                self.template_blacklist = [
                    template.lower().strip() 
                    for template in re.findall('\* *\[\[.*?:(.*?)\]\]', raw)
                ]
            
    def login(self, username, password, domain=None):
        return self.api_helper.login(username, password, domain=domain)
    
    def getURL(self, title, revision=None):
        name = urllib.quote(title.replace(" ", "_").encode('utf-8'), safe=':/@')
        if revision is None:
            return '%sindex%s?title=%s' % (
                self.api_helper.base_url,
                self.api_helper.script_extension,
                name,
            )
        else:
            return '%sindex%s?title=%s&oldid=%s' % (
                self.api_helper.base_url,
                self.api_helper.script_extension,
                name,
                revision,
            )
    
    def getAuthors(self, title, revision=None, max_num_authors=10):
        """Return at most max_num_authors names of non-bot, non-anon users for
        non-minor changes of given article (before given revsion).
        
        @returns: list of principal authors
        @rtype: [unicode]
        """

        for rvlimit in (500, 50):
            result = self.api_helper.page_query(
                titles=title,
                redirects=1,
                prop='revisions',
                rvprop='user|ids|flags|comment',
                rvlimit=rvlimit,
            )
            if result is not None:
                break
        else:
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
        
        if ":" in name:
            name = name.split(':', 1)[1]
        
        if name.lower() in self.template_blacklist:
            log.info("ignoring blacklisted template:" , repr(name))
            return None
        
        try:
            return self.template_cache[name]
        except KeyError:
            pass
        
        titles = ['Template:%s' % name]
        if self.print_template:
            titles.insert(0, self.print_template % name)
        for title in titles:
            raw = self.getRawArticle(title)
            if raw is None:
                continue
            
            if self.template_exclusion_category:
                page = self.api_helper.page_query(
                    titles=title,
                    redirects=1,
                    prop='categories',
                )
                if page is None:
                    log.warn('Could not get categories for template %r' % title)
                    continue
                if 'categories' in page:
                    categories = [
                        c.get('title', '').split(':', 1)[-1]
                        for c in page['categories']
                    ]
                    if self.template_exclusion_category in categories:
                        log.info('Skipping excluded template %r' % title)
                        continue
            
            self.template_cache[name] = raw
            return raw
        
        log.warn('Could not fetch template %r' % name)
        self.template_cache[name] = None
        return None
    
    def getRawArticle(self, title, revision=None):
        if not title:
            return None

        if revision is None:
            page = self.api_helper.page_query(
                titles=title,
                redirects=1,
                prop='revisions',
                rvprop='content',
            )
        else:
            page = self.api_helper.page_query(
                revids=revision,
                prop='revisions',
                rvprop='content',
            )
            if page['title'] != title: # given revision could point to another article!
                return None
        if page is None:
            return None
        revisions = page.get('revisions')
        if revisions is None:
            return None
        if isinstance(revisions, list):
            try:
                return revisions[0]['*']
            except (IndexError, KeyError):
                return None
        else:
            # MediaWiki 1.10
            try:
                return revisions.values()[0]['*']
            except (AttributeError, IndexError, KeyError):
                return None
    
    def getSource(self, title, revision=None):
        """Return source for given article title and revision. For this WikiDB,
        the paramaters are not used.
        
        @returns: source dict
        @rtype: dict
        """
        
        if self.source is not None:
            return self.source
        result = self.api_helper.query(meta='siteinfo')
        if result is None:
            return None
        try:
            g = result['general']
            self.source = metabook.make_source(
                url=g['base'],
                name='%s (%s)' % (g['sitename'], g['lang']),
                language=g['lang'],
            )
            self.getInterwikiMap(title, revision=revision)
            if self.interwikimap:
                self.source['interwikimap'] = self.interwikimap
            return self.source
        except KeyError:
            return None
    
    def getInterwikiMap(self, title, revision=None):
        """Return interwiki map for article with given title and revision
        (the parameters are not used with this WikiDB).
        Fetch it via MediaWiki API if needed.
        
        @returns: interwikimap, i.e. dict mapping prefixes to interwiki data
        @rtype: dict
        """
        
        if hasattr(self, 'interwikimap'):
            return self.interwikimap
        self.interwikimap = {}
        result = self.api_helper.query(
            meta='siteinfo',
            siprop='interwikimap',
        ).get('interwikimap', [])
        if not result:
            return
        for entry in result:
            interwiki = metabook.make_interwiki(api_entry=entry)
            self.interwikimap[interwiki['prefix']] = interwiki
        return self.interwikimap
    
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
    
