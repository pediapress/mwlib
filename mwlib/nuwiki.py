
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
    _siteinfo = None
    def __init__(self, path):
        self.path = os.path.expanduser(path)
        self.revisions = {}
        self._read_revisions()
        
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
        if self._siteinfo is None:
            p = self._pathjoin("siteinfo.json")
            if self._exists(p):
                self._siteinfo = json.load(open(p, "rb"))
        return self._siteinfo
    
    def get_page(self, name, revision=None):
        try:
            if revision is not None:
                return self.revisions[revision]
            return self.revisions[name]
        except KeyError:
            return None
        


        
class adapt(object):
    def __init__(self, path_or_instance):
        if isinstance(path_or_instance, basestring):
            self.nuwiki = nuwiki(path_or_instance)
        else:
            self.nuwiki = path_or_instance
        self.siteinfo = self.nuwiki.get_siteinfo()
        self.nsmapper = nshandling.nshandler(self.siteinfo)
        
    def __getattr__(self, name):
        print "MISSING ATTRBUTE:", name
        raise AttributeError()
    
        
    def getTemplate(self, title, followRedirects=True):
        fqtitle = self.nsmapper.get_fqname(title, defaultns=10)
        p = self.nuwiki.get_page(fqtitle)
        if p:
            return p.rawtext
        
            
    def getRawArticle(self, title, revision=None):
        fqtitle = self.nsmapper.get_fqname(title, defaultns=0)
        p = self.nuwiki.get_page(fqtitle)
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
        lang = None
        # source = self.getSource(title, revision=revision)
        # if source is not None:
        #     lang = source.get('language')
        from mwlib import uparser
        
        return uparser.parseString(title=title, raw=raw, wikidb=self, lang=lang)

    def getLinkURL(self, link, title, revision=None):
        return "http://" + link.target
        
