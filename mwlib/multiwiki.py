#! /usr/bin/env python

# another hack

import os
import tempfile
import binascii
import json
from mwlib import nuwiki

class wiki(nuwiki.adapt):
    magic = binascii.hexlify(os.urandom(8))
    
    def __init__(self, zf):
        self.tmpdir = tmpdir = tempfile.mkdtemp()
        # print "using",  tmpdir
        zf.extractall(tmpdir)
        self.prefix2wiki = {}
        self.current_wiki = None
        self.nuwiki = self
        self.metabook = self.get_data("metabook")
        self.nfo = self.get_data("nfo")
        if self.metabook:
            for x in self.metabook["items"]:
                x["title"] = self.magic+x["title"]
                if "dispaytitle" not in x:
                    x["displaytitle"] = x["title"].split(":", 1)[1]
                    
    @property
    def siteinfo(self):
        if self.current_wiki:
            return self.current_wiki.siteinfo
        return {}
    
    def _get_nuwiki_by_prefix(self, prefix):
        if prefix is None:
            return None
        
        if prefix not in self.prefix2wiki:
            p = os.path.join(self.tmpdir, prefix)
            if os.path.exists(p):
                n = nuwiki.adapt(nuwiki.nuwiki(p))
            else:
                n = None
            self.prefix2wiki[prefix]=n
            
        return self.prefix2wiki[prefix]
    
    def get_siteinfo(self):
        if self.current_wiki:
            return self.current_wiki.get_siteinfo()
        else:
            return {}
        
    siteinfo = property(get_siteinfo)
    @property
    def nshandler(self):
        return self.current_wiki.nshandler
    
    def get_data(self, name):
        fp = os.path.join(self.tmpdir, name+".json")
        if os.path.exists(fp):
            return json.load(open(fp))
        return None
    
    def clear(self):
        pass

    def _switch_to_prefix(self, title):
        if not title.startswith(self.magic):
            return title
        
        prefix, title = title[len(self.magic):].split(":", 1)
        
        n = self._get_nuwiki_by_prefix(prefix)
        if n is not None:
            self.current_wiki = n
        
        return title
        
    def normalize_and_get_page(self, title,  defaultns=0):
        # print "normalize and get_page:", repr(title)
        
        if title.startswith(self.magic):
            prefix, name = title[len(self.magic):].split(":", 1)
        else:
            prefix=None
            name = title
            assert self.current_wiki
            
        n = self._get_nuwiki_by_prefix(prefix)
        if n is not None:
            self.current_wiki = n
            return self.current_wiki.normalize_and_get_page(name,  defaultns=defaultns)
            
        return self.current_wiki.normalize_and_get_page(title, defaultns=defaultns)

    def __getattr__(self, name):
        if self.current_wiki:
            return getattr(self.current_wiki, name)
        
        raise AttributeError("multiwiki has no attribute %r" % (name, ))
    
    def getSource(self, title, revision=None):
        title = self._switch_to_prefix(title)
        return self.current_wiki.getSource(title, revision=revision)
        
    def getParsedArticle(self, title, revision=None):
        title = self._switch_to_prefix(title)
        return nuwiki.adapt.getParsedArticle(self, title, revision=revision)
    
        
