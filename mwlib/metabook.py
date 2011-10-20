#! /usr/bin/env python

# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

import warnings
from collections import deque
from hashlib import md5

import copy

def parse_collection_page(txt):
    from mwlib.parse_collection_page import parse_collection_page
    return parse_collection_page(txt)

class mbobj(object):
    def __init__(self, **kw):
        d = dict(type=self.__class__.__name__)
        
        for k in dir(self.__class__):
            if k.startswith("__"):
                continue
            v = getattr(self.__class__, k)
            if callable(v) or v is None:
                continue
            if isinstance(v, (property, )):
                continue
            
            d[k] = v
            
        self.__dict__.update(copy.deepcopy(d))
        self.__dict__.update(kw)
        self.type = self.__class__.__name__
        
    def __getitem__(self, key):
        warnings.warn("deprecated __getitem__ [%r]" % (key,), DeprecationWarning, 2)
    
        try:
            return getattr(self, str(key))
        except AttributeError:
            raise KeyError(repr(key))
    
    def __setitem__(self, key, val):
        warnings.warn("deprecated __setitem__ [%r]=" % (key, ), DeprecationWarning, 2)
        
        self.__dict__[key]=val

    def __contains__(self,  key):
        warnings.warn("deprecated __contains__ %r in " % (key, ), DeprecationWarning, 2)
        val = getattr(self, str(key), None)
        return val is not None
        
    def get(self, key, default=None):
        warnings.warn("deprecated call get(%r)" % (key, ), DeprecationWarning, 2)
        try:
            val = getattr(self, str(key))
            if val is None:
                return default
            return val
        except AttributeError:
            return default
        
    def _json(self):
        d = dict(type=self.__class__.__name__)
        for k, v in self.__dict__.items():
            if v is not None and not k.startswith("_"):
                d[k]=v
        return d
    
    def __repr__(self):
        return "<%s %r>" % (self.__class__.__name__,  self.__dict__)

class wikiconf(mbobj):
    baseurl = None
    ident = None
    def __init__(self, env=None, pages=None, **kw):
        mbobj.__init__(self, **kw)
        
                 
class collection(mbobj):
    title = None
    subtitle=None
    editor = None
    cover_image = None
    cover_color = None
    text_color = None
    description = None
    sort_as = None

    version = 1
    summary = ""
    items = []
    licenses = []
    wikis = []
    _env = None
    
    def append_article(self, title, displaytitle=None, **kw):
        title = title.strip()
        if displaytitle is not None:
            displaytitle = displaytitle.strip()
        art = article(title=title, displaytitle=displaytitle,  **kw)

        if self.items and isinstance(self.items[-1], chapter):
            self.items[-1].items.append(art)
        else:
            self.items.append(art)
    
    def dumps(self):
        from mwlib import myjson
        return myjson.dumps(self, sort_keys=True, indent=4)
    
    def walk(self,  filter_type=None):
        todo = deque(self.items)
        res = []
        while todo:
            elem = todo.popleft()
            if not filter_type or elem.type == filter_type:
                res.append(elem)
            items = getattr(elem, "items", None)
            if items:
                todo.extendleft(items[::-1])
        return res

    def articles(self):
        return self.walk("article")

    def set_environment(self, env):
        if env.wikiconf:
            self.wikis.append(env.wikiconf)
            
        for x in self.articles():
            if x._env is None:
                x._env = env

    def get_wiki(self, ident=None, baseurl=None):
        assert ident is not None or baseurl is not None
        assert ident is None or baseurl is None

        for wikiconf in self.wikis:
            if ident is not None and wikiconf.ident == ident:
                return wikiconf
            if baseurl is not None and wikiconf.baseurl == baseurl:
                return wikiconf
        return None
                
class source(mbobj):
    name=None
    url=None
    language=None
    base_url=None
    script_extension=None
    locals = None
    system="MediaWiki"
    namespaces = None
    

class interwiki(mbobj):
    local=False

class custom(mbobj):
    title=None
    content=None
    content_type='text/x-wiki'

class article(mbobj):
    title=None
    displaytitle=None
    revision=None
    content_type="text/x-wiki"
    wikiident=None
    _env = None

    @property
    def wiki(self):
        return self._env.wiki

    @property
    def images(self):
        return self._env.images
    
class license(mbobj):
    title=None
    wikitext=None
    
class chapter(mbobj):
    items=[]
    title=u''


# ==============================================================================


def append_article(article, displaytitle, metabook, revision=None):
    metabook.append_article(article, displaytitle, revision=revision)

def get_item_list(metabook, filter_type=None):
    """Return a flat list of items in given metabook
    
    @param metabook: metabook dictionary
    @type metabook: dict
    
    @param filter_type: if set, return only items with this type
    @type filter_type: basestring
    
    @returns: flat list of items
    @rtype: [{}]
    """
    return metabook.walk(filter_type=filter_type)

def calc_checksum(metabook):
    return md5(metabook.dumps()).hexdigest() 
    
def get_licenses(metabook):
    """Return list of licenses
    
    @returns: list of dicts with license info
    @rtype: [dict]
    """
    import re
    from mwlib import utils
    retval = []
    for l in metabook.licenses:
        wikitext = ''

        if l.get('mw_license_url'):
            url = l['mw_license_url']
            if re.match(r'^.*/index\.php.*action=raw', url) and 'templates=expand' not in url:
                url += '&templates=expand'
            wikitext = utils.fetch_url(url,
                ignore_errors=True,
                expected_content_type='text/x-wiki',
            )
            if wikitext:
                try:
                    wikitext = unicode(wikitext, 'utf-8')
                except UnicodeError:
                    wikitext = None
        else:
            wikitext = ''
            if l.get('mw_rights_text'):
                wikitext = l['mw_rights_text']
            if l.get('mw_rights_page'):
                wikitext += '\n\n[[%s]]' % l['mw_rights_page']
            if l.get('mw_rights_url'):
                wikitext += '\n\n' + l['mw_rights_url']
        
        if not wikitext:
            continue

        retval.append(license(title=l.get('name', u'License'),
                              wikitext=wikitext))
    
    return retval 

def make_interwiki(api_entry=None):
    api_entry = api_entry or {}
    d={}
    for k, v in api_entry.items():
        d[str(k)] = v
    return interwiki(**d)

make_metabook  = collection
make_chapter   = chapter
make_source    = source
make_article   = article
make_custom    = custom
