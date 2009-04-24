
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.txt for additional licensing information.

import os
import json
import zipfile
import tempfile

from mwlib import nshandling, utils

class page(object):
    def __init__(self, meta, rawtext):
        self.__dict__.update(meta)
        self.rawtext = rawtext
        
class nuwiki(object):
    def __init__(self, path):
        self.path = os.path.expanduser(path)

        self.excluded = set(x.get("title") for x in self._loadjson("excluded.json", []))            
        
        self.revisions = {}
        self._read_revisions()
        
        self.redirects = self._loadjson("redirects.json", {})
        self.siteinfo = self._loadjson("siteinfo.json", {})
        self.nsmapper = nshandling.nshandler(self.siteinfo)        
        self.nfo = self._loadjson("nfo.json", {})
        p = self.nfo.get("print_template_pattern")
        if p and "$1" in p:
            self.make_print_template = utils.get_print_template_maker(p)
        else:
            self.make_print_template = None
            
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
            pg = page(meta, rawtext)
            if pg.title not in self.excluded:
                self.revisions[meta["revid"]] = pg
            # else:
            #     print "excluding:", repr(pg.title)
                
        tmp = self.revisions.items()
        tmp.sort(reverse=True)
        for revid, p in tmp:
            title = p.title
            if title not in self.revisions:
                self.revisions[title] = p
                
    def _pathjoin(self, *p):
        return os.path.join(self.path, *p)
    
    def _exists(self, p):
        return os.path.exists(p)
    
    def get_siteinfo(self):
        return self.siteinfo
    
    def get_page(self, name, revision=None):
        if revision is not None:
            return self.revisions.get(revision)
        
        name = self.redirects.get(name, name)
        
        if self.make_print_template is not None:
            pname = self.make_print_template(name)
            r=self.revisions.get(pname)
            # print "returning print template", repr(pname)
            if r is not None:
                # r.title = name # XXX not so sure about that one???
                return r
            
        return self.revisions.get(name)
    
    def normalize_and_get_page(self, name, defaultns):
        fqname = self.nsmapper.get_fqname(name, defaultns=defaultns)
        return self.get_page(fqname)

    def normalize_and_get_image_path(self, name):
        ns, partial, fqname = self.nsmapper.splitname(name, defaultns=6)
        if ns != 6:
            return

        p = self._pathjoin("images", utils.fsescape(fqname))
        if self._exists(p):
            return p

    def get_data(self, name):
        return self._loadjson(name+".json")
    
    
class adapt(object):
    edits = None
    
    def __init__(self, path_or_instance):
        if isinstance(path_or_instance, zipfile.ZipFile):
            zf = path_or_instance
            tmpdir = tempfile.mkdtemp()
            # os.mkdir(os.path.join(tmpdir, "images"))
            zf.extractall(tmpdir)
            path_or_instance = tmpdir
            
                
        if isinstance(path_or_instance, basestring):
            self.nuwiki = nuwiki(path_or_instance)
        else:
            self.nuwiki = path_or_instance
        self.siteinfo = self.nuwiki.get_siteinfo()
        self.metabook = self.nuwiki.get_data("metabook")
        
    def __getattr__(self, name):
        try:
            return getattr(self.nuwiki, name)
        except AttributeError:
            raise AttributeError()
    
        
    def getTemplate(self, title, followRedirects=True):
        p = self.nuwiki.normalize_and_get_page(title, defaultns=10)
        if p:
            return p.rawtext
            
    def getRawArticle(self, title, revision=None):
        if revision is not None:
            p = self.nuwiki.get_page(None, revision)
        else:
            p = self.nuwiki.normalize_and_get_page(title, defaultns=0)
            
        if p:
            return p.rawtext
        
    def getURL(self, name, revision):
        fqtitle = self.nsmapper.get_fqname(name)
        base = self.siteinfo["general"]["base"]
        return "%s/%s" % (base.rsplit("/", 1)[0], name)
    
    def getAuthors(self, title, revision=None):
        if self.edits is None:
            edits = self.edits = {}
            for edit in self.nuwiki.get_data("edits") or []:
                title = edit.get("title")
                revisions = edit.get("revisions")
                edits[title] = revisions
        
        fqname = self.nsmapper.get_fqname(title)
        revisions = self.edits.get(fqname, [])
        from mwlib.authors import get_authors
        authors = get_authors(revisions)
        return authors
    
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

    def clear(self):
        pass
    
    def getDiskPath(self, name, size=None):
        return self.nuwiki.normalize_and_get_image_path(name)

    def getDescriptionURL(self, name): # for an image
        return "http://"+self.nuwiki.nsmapper.get_fqname(name, 6)
    
        
