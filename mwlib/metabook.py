#! /usr/bin/env python

# Copyright (c) 2007-2009 PediaPress GmbH
# See README.txt for additional licensing information.

import warnings
from collections import deque
try:
    from hashlib import md5
except ImportError:
    from md5 import md5

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
            d[k] = v
            
        self.__dict__.update(copy.deepcopy(d))
        self.__dict__.update(kw)
        self.type = self.__class__.__name__
        
    def __getitem__(self, key):
        warnings.warn("deprecated", DeprecationWarning, 2)
    
        try:
            return getattr(self, str(key))
        except AttributeError:
            raise KeyError(repr(key))
    
    def __setitem__(self, key, val):
        warnings.warn("deprecated", DeprecationWarning, 2)
        
        self.__dict__[key]=val

    def __contains__(self,  key):
        warnings.warn("deprecated", DeprecationWarning, 2)
        val = getattr(self, str(key), None)
        return val is not None
        
    def get(self, key, default=None):
        warnings.warn("deprecated", DeprecationWarning, 2)
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
    
class collection(mbobj):
    title = None
    subtitle=None
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
        for x in self.articles():
            if x._env is None:
                x._env = env
                
        
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

class article(mbobj):
    title=None
    displaytitle=None
    revision=None
    content_type="text/x-wiki"
    wikiident=None
    _env = None
    
class chapter(mbobj):
    items=[]
    title=None


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
    licenses = []
    for license in metabook.licenses:
        wikitext = ''

        if license.get('mw_license_url'):
            url = license['mw_license_url']
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
            if license.get('mw_rights_text'):
                wikitext = license['mw_rights_text']
            if license.get('mw_rights_page'):
                wikitext += '\n\n[[%s]]' % license['mw_rights_page']
            if license.get('mw_rights_url'):
                wikitext += '\n\n' + license['mw_rights_url']
        
        if not wikitext:
            continue
        
        licenses.append({
            'title': license.get('name', u'License'),
            'wikitext': wikitext,
        })
    
    return licenses

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
