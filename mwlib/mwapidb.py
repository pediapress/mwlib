#! /usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) PediaPress GmbH
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

try:
    import json
except ImportError:
    import simplejson as json

from mwlib import utils, metabook, wikidbbase, uparser, parser, namespace, advtree
from mwlib.expander import find_template, get_template_args, Expander
from mwlib.log import Log
from mwlib.templ import mwlocals

log = Log("mwapidb")

# ==============================================================================

class MWAPIError(RuntimeError):
    """MediaWiki API error"""

class QueryWarningError(RuntimeError):
    """MediaWiki API query contained warning"""

# ==============================================================================

articleurl_rex = re.compile(r'^(?P<scheme_host_port>https?://[^/]+)(?P<path>.*)$')
api_helper_cache = {}

def get_api_helper(url, offline=False):
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

    path_prefix = ''
    if '/wiki/' in path:
        path_prefix = path[:path.find('/wiki/')]
    elif '/w/' in path:
        path_prefix = path[:path.find('/w/')]
    
    prefix = '%s://%s%s' % (scheme, netloc, path_prefix)
    try:
        return api_helper_cache[prefix]
    except KeyError:
        pass

    for path in ('/w/', '/wiki/', '/'):
        base_url = '%s%s' % (prefix, path)
        api_helper = APIHelper(base_url)
        if offline or api_helper.is_usable():
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
    
    # Wikitravel special case:
    if netloc == 'wikitravel.org':
        mo = re.match(r'^/(?P<lang>.+?)/(?P<title>.*)$', path)
        if mo:
            api_helper = APIHelper('%s://%s/wiki/%s/' % (
                scheme, netloc, mo.group('lang'),
            ))
            if api_helper.is_usable():
                return {
                    'api_helper': api_helper,
                    'title': unicode(
                        urllib.unquote(mo.group('title')),
                        title_encoding,
                        'ignore'
                    ).replace('_', ' '),
                    'revision': None,
                }

    api_helper = get_api_helper(url)
    if api_helper is None:
        return None

    for part in ('index.php/', '/wiki/'):
        if part in path:
            return {
                'api_helper': api_helper,
                'title': unicode(
                    urllib.unquote(path[path.find(part) + len(part):]),
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
    
    def __init__(self, base_url, script_extension=None, offline=False):
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
        if not offline:
            self.opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookielib.CookieJar()))
            self.opener.addheaders = [('User-agent', 'mwlib')]

    def __repr__(self):
        return "<%s at %s baseurl=%s>" %(self.__class__.__name__, id(self), self.base_url) 

    def getURL(self, title, revision=None):
        name = urllib.quote_plus(title.replace(" ", "_").encode('utf-8'), safe=':/@')
        if revision is None:
            return '%sindex%s?title=%s' % (
                self.base_url,
                self.script_extension,
                name,
            )
        else:
            return '%sindex%s?oldid=%s' % (
                self.base_url,
                self.script_extension,
                revision,
            )
    
    def is_usable(self):
        result = self.query(meta='siteinfo', ignore_errors=True)
        if result is None:
            return False
        result = result['query']
        if 'general' in result:
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
        result = json.loads(unicode(result, 'utf-8'))
        if 'login' in result and result['login'].get('result') == 'Success':
            return True
        return False
    
    def do_request(self, ignore_errors=True, num_tries=2, **kwargs):
        args = {'format': 'json'}
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
            return json.loads(data)
        except Exception, e:
            log.error('Got exception: %r' % e)
            if ignore_errors:
                return None
            raise RuntimeError('api%s request failed. Are you sure you specified the correct base URL?' % self.script_extension)
    
    def query(self, ignore_errors=True, num_tries=2, **kwargs):
        data = self.do_request(ignore_errors=ignore_errors, num_tries=num_tries, action='query', **kwargs)
        if data is None:
            return None
        if 'query' not in data:
            return None
        if 'warnings' in data:
            raise QueryWarningError('Query result contained warning: %r' % data)
        return data
    
    def page_query(self, **kwargs):
        q = self.query(**kwargs)
        if q is not None:
            try:
                return q['query']['pages'].values()[0]
            except (KeyError, IndexError):
                return None
        return None

    def content_query(self, title):
        'quick and dirty content query'
        r = self.page_query(**dict(titles=title ,prop='revisions',rvprop='content'))
        if r and 'revisions' in r:
            return r['revisions'][0]['*']

    

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
        
        api_helper = get_api_helper(desc_url)
        if api_helper is None:
            if wikidb is not None:
                api_helper = wikidb.api_helper
            else:
                return []
        
        result = api_helper.page_query(titles='Image:%s' % name, prop='templates', tllimit='500')
        if not result or 'templates' not in result:
            return []
        
        try:
            return [t['title'].split(':', 1)[-1] for t in result['templates']]
        except KeyError:
            return []

    def getContributorsFromInformationTemplate(self, raw, title, wikidb):
                
        def getUserLinks(raw):
            def isUserLink(node):
                return isinstance(node, parser.NamespaceLink) and node.namespace == namespace.NS_USER
            
            result = list(set([
                u.target
                for u in uparser.parseString(title,
                    raw=raw,
                    wikidb=wikidb,
                ).filter(isUserLink)
            ]))
            result.sort()
            return result
            
        expander = Expander(u'', title, wikidb)       
        template = find_template(raw, 'Information')
        if template is not None:
            author = get_template_args(template, expander).get('Author', '').strip()
            if author:
                users = getUserLinks(author)
                if users:
                    users = list(set(users))
                    users.sort()
                    return users
                
                node = uparser.parseString('', raw=author, wikidb=wikidb)
                advtree.extendClasses(node)
                return [node.getAllDisplayText()]
        
        return getUserLinks(raw)


    
    def getContributors(self, name, wikidb=None):
        """Return list of image contributors
        
        @param name: image name without namespace (e.g. without "Image:")
        @type name: unicode
        
        @param wikidb: WikiDB instance (optional)
        @type wikidb: object
        
        @returns: list of contributors
        @rtype: [unicode] or None
        """
        
        desc_url = self.getDescriptionURL(name)
        if desc_url is None:
            return None
        
        # Note: We're always guessing the API helper b/c we'll get problems when
        # fetching from en.wp if we should've used commons.wikimedia.org instead.
        # A passed wikidb is only used as a fallback here.
        api_helper = get_api_helper(desc_url)
        if api_helper is None:
            if wikidb is None:
                return None
        else:
            wikidb = WikiDB(api_helper=api_helper)
        
        title = 'Image:%s' % name
        
        raw = wikidb.getRawArticle(title)
        if not raw:
            return None
        users = self.getContributorsFromInformationTemplate(raw, title, wikidb)
        if users:
            return users
        
        return wikidb.getAuthors(title)
    

# ==============================================================================

    
class WikiDB(wikidbbase.WikiDBBase):
    ip_rex = re.compile(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$')
    bot_rex = re.compile(r'bot', re.IGNORECASE)
    redirect_rex = re.compile(r'^#redirect:?\s*?\[\[.*?\]\]', re.IGNORECASE)
    magicwords = None
    def __init__(self,
        base_url=None,
        username=None,
        password=None,
        domain=None,
        template_blacklist=None,
        template_exclusion_category=None,
        print_template_pattern=None,
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
        
        @param print_template_pattern: pattern for print templates (optional)
        @type print_template_pattern: unicode
        
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
            pattern=print_template_pattern,
        )
        self.source = None
    
    def setTemplateExclusion(self, blacklist=None, category=None, pattern=None):
        self.template_exclusion_category = category
        if pattern is not None and '$1' not in pattern:
            pattern = '%s$1' % pattern
            log.warn('print template pattern does not contain "$1", using %r.' % pattern)
        self.print_template_pattern = pattern
        self.template_blacklist = []
        if blacklist:
            raw = self.getRawArticle(blacklist)
            if raw is None:
                log.error('Could not get template blacklist article %r' % (
                    blacklist,
                ))
            else:
                self.template_blacklist = [
                    template.lower().strip().replace('_', ' ')
                    for template in re.findall('\* *\[\[.*?:(.*?)\]\]', raw) # FIXME
                ]
            
    def login(self, username, password, domain=None):
        return self.api_helper.login(username, password, domain=domain)
    
    def getURL(self, title, revision=None):
        return self.api_helper.getURL(title, revision=revision)
    
    def getAuthors(self, title, revision=None, _rvlimit=500):
        """Return names of non-bot, non-anon users for
        non-minor changes of given article (before given revsion).
        
        The data that can be used to to compute a list of authors is limited:
        http://de.wikipedia.org/w/api.php?action=query&prop=revisions&rvlimit=500&
        rvprop=ids|timestamp|flags|comment|user|size&titles=Claude_Bourgelat
        
        Authors are sorted by the approximate size of their contribution.
        
        Edits are considered to be reverts if two edits end up in the sames size within 
        N edits and have the reverting edit has the revid of the reverted edit in its commet.
        
        @returns: sorted list of principal authors
        @rtype: list([unicode])
        """

        REVERT_LOOKBACK = 5 # number of revisions to check for same size (assuming a revert)
        USE_DIFF_SIZE = False # whether to sort by diffsize or by alphabet
        FILTER_REVERTS = False # can not be used if 
        
        kwargs = {
            'titles': title,
            'redirects': 1,
            'prop': 'revisions',
            'rvprop': 'ids|user|flags|comment|size',
            'rvlimit': _rvlimit,
            'rvdir': 'older',
        }
        if revision is not None:
            kwargs['rvstartid'] = revision
        result = self.api_helper.query(**kwargs)
        if result is None:
            if _rvlimit > 50:
                # some MWs only return the 50 last edits 
                return self.getAuthors(title, revision=revision, _rvlimit=50)
            return None

        try:
            revs = result['query']['pages'].values()[0]['revisions']
        except (KeyError, IndexError):
            return None

        while 'query-continue' in result:
            try:
                kwargs['rvstartid'] = result['query-continue']['revisions']['rvstartid']
            except KeyError:
                log.error('Got bogus query-continuation from API')
                break
            result = self.api_helper.query(**kwargs)
            if result is None:
                log.error('Query continuation failed.')
                break
            try:
                revs.extend(result['query']['pages'].values()[0]['revisions'])
            except (KeyError, IndexError):
                log.error('Query continuation failed.')
                break

        def filter_reverts(revs):
            # Start with oldest edit:
            # (note that we can *not* just pass rvdir=newer to API, because if we
            # have a given article revision, we have to get revisions older than
            # that)
            revs.reverse() 
            # remove revs w/o size (happens with move)
            revs = [r for r in revs if "size" in r]
            for i, r in enumerate(revs):
                if "reverted" in r or i==0:
                    continue
                last_size = revs[i-1]['size']
                for j in range(i+1,min(len(revs)-1, i+REVERT_LOOKBACK+1)):
                    if revs[j]['size'] == last_size and str(r['revid']) in revs[j].get('comment',''): 
                        for jj in range(i,j+1): # skip the reverted, all in between, and the reverting edit 
                            revs[jj]['reverted'] = True 
                        break
            #print "reverted", [r for r in revs if "reverted" in r]
            return [r for r in revs if not "reverted" in r]

        if FILTER_REVERTS:
            revs = list(filter_reverts(revs))

        # calc an approximate size for each edit (true if author only *added* to the article)
        if USE_DIFF_SIZE:
            for i, r in enumerate(revs):
                if i == 0:
                    r['diff_size'] = r['size']
                else:
                    r['diff_size'] = abs(r['size']-revs[i-1]['size'])

        ANON = "ANONIPEDITS"
        authors = dict() # author:bytes
        for r in revs:
            if 'minor' in r:  
                pass # include minor edits
            user = r.get('user', u'')
            if 'anon' in r and (not user or self.ip_rex.match(user)): # anon
                authors[ANON] = authors.get(ANON, 0) + 1
            elif not user:
                continue
            elif self.bot_rex.search(user) or self.bot_rex.search(r.get('comment', '')):
                continue # filter bots
            else:
                if USE_DIFF_SIZE:
                    authors[user] = authors.get(user, 0) + abs(r['diff_size'])
                else:
                    authors[user] = authors.get(user, 0) + 1
        
        num_anon = authors.get(ANON, 0)
        try:
            del authors[ANON]
        except KeyError:
            pass
       
        if USE_DIFF_SIZE: # by summarized edit diff sizes
            authors = authors.items()
            authors.sort(lambda a,b:cmp(b[1], a[1]))
        else: # sorted by A-Z
            authors = authors.items()
            authors.sort()

        # append anon
        authors.append((("%s:%d"  % (ANON,num_anon),num_anon)))  #  append at the end
#        print authors
        return [a for a,c in authors]

    def getTemplate(self, name, followRedirects=True):
        """
        Note: *Not* following redirects is unsupported!
        """

        ns, name, full = namespace.splitname(name, namespace.NS_TEMPLATE)
        if ns!=namespace.NS_TEMPLATE:
            return self.getRawArticle(full)
        
        if name.replace('_', ' ').lower() in self.template_blacklist:
            log.info("ignoring blacklisted template:" , repr(name))
            return None
        
        try:
            return self.template_cache[name]
        except KeyError:
            pass
        
        titles = [u'Template:%s' % name]
        if self.print_template_pattern:
            titles.insert(0, u'Template:%s' % (self.print_template_pattern.replace(u'$1', name),))
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
            if page is not None and page['title'] != title: # given revision could point to another article!
                return None
        if page is None:
            return None
        revisions = page.get('revisions')
        if revisions is None:
            return None
        if isinstance(revisions, list):
            try:
                raw = revisions[0]['*']
                if revision and self.redirect_rex.search(raw):
                    return self.getRawArticle(title) # let getRawArticle() w/out revision do the redirect handling
                return raw
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
        try:
            result = self.api_helper.query(meta='siteinfo', siprop='general|namespaces|namespacealiases|magicwords')
        except QueryWarningError:
            result = self.api_helper.query(meta='siteinfo', siprop='general|namespaces|namespacealiases')
        if result is None:
            return None
        result = result['query']
        try:
            g = result['general']
            self.source = metabook.make_source(
                url=g['base'],
                name='%s (%s)' % (g['sitename'], g['lang']),
                language=g['lang'],
                base_url=self.api_helper.base_url,
                script_extension=self.api_helper.script_extension,
            )
            self.getInterwikiMap(title, revision=revision)
            if self.interwikimap:
                self.source['interwikimap'] = self.interwikimap
            self.getLocals()
            if self.locals:
                self.source['locals'] = self.locals
            self.source['magicwords'] = result.get('magicwords')
            self.source['namespaces'] = result['namespaces']
            self.source['namespacealiases'] = result['namespacealiases']
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
        )
        if not result:
            return
        result = result['query']
        result = result.get('interwikimap', [])
        if not result:
            return
        for entry in result:
            interwiki = metabook.make_interwiki(api_entry=entry)
            self.interwikimap[interwiki['prefix'].lower()] = interwiki
        return self.interwikimap
    
    def getParsedArticle(self, title, revision=None):
        raw = self.getRawArticle(title, revision=revision)
        if raw is None:
            return None
        a = uparser.parseString(title=title, raw=raw, wikidb=self)
        return a

    def getMagicwords(self, source_url=None):
        if self.magicwords is None:
            res = self.api_helper.do_request(action='query', meta='siteinfo', siprop='magicwords')
            try:
                self.magicwords = res['query']['magicwords']
            except KeyError:
                self.magicwords = []
        return self.magicwords
            
    def getLocals(self, source_url=None):
        if hasattr(self, 'locals'):
            return self.locals
        result = self.api_helper.do_request(
            action='expandtemplates',
            text=mwlocals.get_locals_txt(),
        )
        try:
            self.locals = result['expandtemplates']['*']
        except (KeyError, TypeError):
            self.locals = None
        return self.locals
    

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
    
