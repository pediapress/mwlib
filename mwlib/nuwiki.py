
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.txt for additional licensing information.

import os
import json

from mwlib import nshandling


class page(object):
    def __init__(self, meta, rawtext):
        self.__dict__.update(meta)
        self.rawtext = rawtext
        
class nuwiki(object):
    def __init__(self, path):
        self.path = os.path.expanduser(path)
        self.revisions = {}
        self._read_revisions()
        
        self.redirects = self._loadjson("redirects.json", {})
        self.siteinfo = self._loadjson("siteinfo.json", {})
        self.nsmapper = nshandling.nshandler(self.siteinfo)        
        
    def _loadjson(self, path, default=None):
        path = self._pathjoin(path)
        if self._exists(path):
            return json.load(open(path, "rb"))
        return default
        
    def _read_revisions(self):
        d=unicode(open(self._pathjoin("revisions-1.txt"), "rb").read(), "utf-8")
        pages = d.split("\n --page-- ")

        for p in pages[1:]:
            jmeta, rawtext = p.split("\n", 1)
            meta = json.loads(jmeta)            
            self.revisions[meta["revid"]] = page(meta, rawtext)

        tmp = self.revisions.items()
        tmp.sort(reverse=True)
        for revid, p in tmp:
            title = p.title
            if title not in self.revisions:
                self.revisions[title] = p
        
    def _pathjoin(self, p):
        return os.path.join(self.path, p)
    
    def _exists(self, p):
        return os.path.exists(p)
    
    def get_siteinfo(self):
        return self.siteinfo
    
    def get_page(self, name, revision=None):
        if revision is not None:
            return self.revisions.get(revision)
        
        name = self.redirects.get(name, name)
        return self.revisions.get(name)
    
    def normalize_and_get_page(self, name, defaultns):
        fqname = self.nsmapper.get_fqname(name, defaultns=defaultns)
        return self.get_page(fqname)
    
    
class adapt(object):
    def __init__(self, path_or_instance):
        if isinstance(path_or_instance, basestring):
            self.nuwiki = nuwiki(path_or_instance)
        else:
            self.nuwiki = path_or_instance
        self.siteinfo = self.nuwiki.get_siteinfo()
        
    def __getattr__(self, name):
        try:
            return getattr(self.nuwiki, name)
        except AttributeError:
            print "MISSING ATTRBUTE:", name
            raise AttributeError()
    
        
    def getTemplate(self, title, followRedirects=True):
        p = self.nuwiki.normalize_and_get_page(title, defaultns=10)
        if p:
            return p.rawtext
            
    def getRawArticle(self, title, revision=None):
        if revision is not None:
            return self.nuwiki.get_page(None, revision)
        p = self.nuwiki.normalize_and_get_page(title, defaultns=0)
        if p:
            return p.rawtext
        
    def getURL(self, name, revision):
        fqtitle = self.nsmapper.get_fqname(name)
        base = self.siteinfo["general"]["base"]
        return "%s/%s" % (base.rsplit("/", 1)[0], name)
    
    def getAuthors(self, title, revision=None):
        return None

    def getSource(self, title, revision=None):
        res = {}
        res["script_extension"] = ".php"
        res["type"] = "source"
        res["url"] = self.siteinfo["general"]["base"]
        res["base_url"] = res["url"]
        res["name"] = self.siteinfo["general"]["lang"]
        
        return res

    def getParsedArticle(self, title, revision=None):
        raw = self.getRawArticle(title, revision=revision)
        if raw is None:
            return None
        si = self.nuwiki.get_siteinfo()
        lang = si["general"]["lang"]
        
        from mwlib import uparser        
        return uparser.parseString(title=title, raw=raw, wikidb=self, lang=lang)

    def getLinkURL(self, link, title, revision=None):
        return "http://" + link.target
        
    def getLicenses(self):
        return []
    
