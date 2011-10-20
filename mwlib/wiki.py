#! /usr/bin/env python

# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

import os
from ConfigParser import ConfigParser
import StringIO

from mwlib.log import Log
from mwlib import myjson
from mwlib.metabook import wikiconf

log = Log('mwlib.utils')
    

def wiki_obsolete_cdb(path=None,  **kwargs):
    raise RuntimeError("cdb file format has changed. please rebuild with mw-buildcdb")

def wiki_nucdb(path=None, lang="en", **kwargs):
    from mwlib import cdbwiki,  nuwiki
    path = os.path.expanduser(path)
    db=cdbwiki.WikiDB(path, lang=lang)
    return nuwiki.adapt(db)



dispatch = dict(
    wiki = dict(cdb=wiki_obsolete_cdb, nucdb=wiki_nucdb)
)

_en_license_url = 'http://en.wikipedia.org/w/index.php?title=Help:Books/License&action=raw'
wpwikis = dict(
    de = dict(baseurl='http://de.wikipedia.org/w/', 
              mw_license_url='http://de.wikipedia.org/w/index.php?title=Hilfe:Buchfunktion/Lizenz&action=raw'),
    en = dict(baseurl='http://en.wikipedia.org/w/', mw_license_url=_en_license_url),
    fr = dict(baseurl='http://fr.wikipedia.org/w/', mw_license_url=None),
    es = dict(baseurl='http://es.wikipedia.org/w/', mw_license_url=None),
    pt = dict(baseurl='http://pt.wikipedia.org/w/', mw_license_url=None),
    enwb = dict(baseurl='http://en.wikibooks.org/w', mw_license_url=_en_license_url),
    commons = dict(baseurl='http://commons.wikimedia.org/w/', mw_license_url=_en_license_url)
    )


class Environment(object):
    wikiconf = None
    
    def __init__(self, metabook=None):
        self.metabook = metabook
        self.images = None
        self.wiki = None
        self.configparser = ConfigParser()
        defaults=StringIO.StringIO("""
[wiki]
name=
url=
""")
        self.configparser.readfp(defaults)
    
    def init_metabook(self):
        if self.metabook:
            self.metabook.set_environment(self)

    def getLicenses(self):
        return self.wiki.getLicenses()
    
class MultiEnvironment(Environment):
    wiki = None
    images = None
    
    def __init__(self, path):
        Environment.__init__(self)
        self.path = path
        self.metabook = myjson.load(open(os.path.join(self.path, "metabook.json")))
        self.id2env = {}
        
    def init_metabook(self):
        from mwlib import nuwiki
        if not self.metabook:
            return
        
        for x in self.metabook.articles():
            id = x.wikiident
            assert id, "article has no wikiident: %r" % (x,)
            assert "/" not in id
            assert ".." not in id
            
            if id not in self.id2env:
                env = Environment()
                env.images = env.wiki = nuwiki.adapt(os.path.join(self.path, id))
                self.id2env[id] = env
            else:
                env = self.id2env[id]
            x._env = env
            
    def getLicenses(self):
        res = list(self.metabook.licenses or [])
        for t in res:
            t._wiki = None
            
        for x in self.id2env.values():
            tmp = x.wiki.getLicenses()
            for t in tmp:
                t._env = x
            res += tmp
        
        return res

def ndict(**kw):
    for k, v in kw.items():
        if v is None:
            del kw[k]
    return kw

def _makewiki(conf, metabook=None, **kw):
    kw = ndict(**kw)
    res = Environment(metabook)
    
    url = None
    if conf.startswith(':'):
        if conf[1:] not in wpwikis:
            wpwikis[conf[1:]] =  dict(baseurl = "http://%s.wikipedia.org/w/" % conf[1:],
                                      mw_license_url =  None)
            

        url = wpwikis.get(conf[1:])['baseurl']

    if conf.startswith("http://") or conf.startswith("https://"):
        url = conf

    if url:
        res.wiki = None
        res.wikiconf = wikiconf(baseurl=url, **kw)
        res.image = None
        return res

    nfo_fn = os.path.join(conf, 'nfo.json')
    if os.path.exists(nfo_fn):
        from mwlib import nuwiki
        from mwlib import myjson as json

        try:
            format = json.load(open(nfo_fn, 'rb'))['format']
        except KeyError:
            pass
        else:
            if format == 'nuwiki':
                res.images = res.wiki = nuwiki.adapt(conf)
                res.metabook = res.wiki.metabook
                return res
            elif format == 'multi-nuwiki':
                return MultiEnvironment(conf)

    if os.path.exists(os.path.join(conf, "content.json")):
        raise RuntimeError("old zip wikis are not supported anymore")

    # yes, I really don't want to type this everytime
    wc = os.path.join(conf, "wikiconf.txt")
    if os.path.exists(wc):
        conf = wc 
        
    if conf.lower().endswith(".zip"):
        import zipfile
        from mwlib import myjson as json
        conf = os.path.abspath(conf)
        
        zf = zipfile.ZipFile(conf)
        try:
            format = json.loads(zf.read("nfo.json"))["format"]
        except KeyError:
            raise RuntimeError("old zip wikis are not supported anymore")

        if format=="nuwiki":
            from mwlib import nuwiki
            res.images = res.wiki = nuwiki.adapt(zf)
            if metabook is None:
                res.metabook = res.wiki.metabook
            return res
        elif format==u'multi-nuwiki':
            from mwlib import nuwiki
            import tempfile
            tmpdir = tempfile.mkdtemp()
            nuwiki.extractall(zf, tmpdir)
            res = MultiEnvironment(tmpdir)
            return res
        else:
            raise RuntimeError("unknown format %r" % (format,))
        
    

    cp = res.configparser
    
    if not cp.read(conf):
        raise RuntimeError("could not read config file %r" % (conf,))

        
    for s in ['images', 'wiki']:
        if not cp.has_section(s):
            continue
        
        args = dict(cp.items(s))
        if "type" not in args:
            raise RuntimeError("section %r does not have key 'type'" % s)
        t = args['type']
        del args['type']
        try:
            m = dispatch[s][t]
        except KeyError:
            raise RuntimeError("cannot handle type %r in section %r" % (t, s))

        setattr(res, s, m(**args))
    
    assert res.wiki is not None, '_makewiki should have set wiki attribute'
    return res

def makewiki(config, metabook=None, **kw):
    if not config:
        res = Environment(metabook)
    else:
        res = _makewiki(config, metabook=metabook, **kw)
        
    if res.wiki:
        res.wiki.env = res
    if res.images:
        res.images.env = res

    res.init_metabook()
    
    return res
