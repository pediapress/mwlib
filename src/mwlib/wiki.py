#! /usr/bin/env python

# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.


import os
from io import StringIO

from six.moves.configparser import ConfigParser

from mwlib import myjson
from mwlib.exceptions.mwlib_exceptions import WikiIdValidationError
from mwlib.log import Log
from mwlib.metabook import WikiConf

log = Log('mwlib.utils')


def wiki_obsolete_cdb(path=None, **kwargs):
    raise RuntimeError("cdb file format is not supported anymore.")


dispatch = {
    'wiki': {'cdb': wiki_obsolete_cdb, 'nucdb': wiki_obsolete_cdb}
}

_en_license_url = 'https://en.wikipedia.org/w/index.php?title=Help:Books/License&action=raw'
wpwikis = {
    'de': {'baseurl': 'https://de.wikipedia.org/w/',
            'mw_license_url': 'https://de.wikipedia.org/w/index.php?title=Hilfe:Buchfunktion/Lizenz&action=raw'},
    'en': {'baseurl': 'https://en.wikipedia.org/w/', 'mw_license_url': _en_license_url},
    'fr': {'baseurl': 'https://fr.wikipedia.org/w/', 'mw_license_url': None},
    'es': {'baseurl': 'https://es.wikipedia.org/w/', 'mw_license_url': None},
    'pt': {'baseurl': 'https://pt.wikipedia.org/w/', 'mw_license_url': None},
    'enwb': {'baseurl': 'https://en.wikibooks.org/w', 'mw_license_url': _en_license_url},
    'commons': {'baseurl': 'https://commons.wikimedia.org/w/', 'mw_license_url': _en_license_url}
}


class Environment:
    wikiconf = None

    def __init__(self, metabook=None):
        self.metabook = metabook
        self.images = None
        self.wiki = None
        self.configparser = ConfigParser()
        defaults = StringIO("""
[wiki]
name=
url=
""")
        self.configparser.read_file(defaults)

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
        with open(os.path.join(self.path, "metabook.json")) as fp:
            self.metabook = myjson.load(fp)
        self.id2env = {}

    def _validate_wiki_id(self, wiki_id, x):
        is_valid = wiki_id
        if not is_valid:
            raise WikiIdValidationError(f"article has no wikiident: {x!r}")
        is_valid = "/" not in wiki_id and ".." not in wiki_id
        if not is_valid:
            raise WikiIdValidationError(f"article has invalid wikiident: {x!r}")

    def init_metabook(self):
        from mwlib import nuwiki
        if not self.metabook:
            return

        for x in self.metabook.articles():
            wiki_id = x.wikiident
            self._validate_wiki_id(wiki_id, x)

            if wiki_id not in self.id2env:
                env = Environment()
                env.images = env.wiki = nuwiki.adapt(os.path.join(self.path, wiki_id))
                self.id2env[wiki_id] = env
            else:
                env = self.id2env[wiki_id]
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


def ndict(**original):
    """Delete all keys with value None from dict."""
    return {k: v for k, v in original.items() if v is not None}


def _makewiki(conf, metabook=None, **kw):
    kw = ndict(**kw)
    res = Environment(metabook)

    url = None
    if conf.startswith(':'):
        if conf[1:] not in wpwikis:
            wpwikis[conf[1:]] = {'baseurl': "http://%s.wikipedia.org/w/" % conf[1:],
                                     'mw_license_url': None}

        url = wpwikis.get(conf[1:])['baseurl']

    if conf.startswith("http://") or conf.startswith("https://"):
        url = conf

    if url:
        res.wiki = None
        res.wikiconf = WikiConf(baseurl=url, **kw)
        res.image = None
        return res

    nfo_fn = os.path.join(conf, 'nfo.json')
    if os.path.exists(nfo_fn):
        from mwlib import myjson as json
        from mwlib import nuwiki

        try:
            with open(nfo_fn, 'rb') as fp:
                format = json.load(fp)['format']
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

        if format == "nuwiki":
            from mwlib import nuwiki
            res.images = res.wiki = nuwiki.adapt(zf)
            if metabook is None:
                res.metabook = res.wiki.metabook
            return res
        elif format == 'multi-nuwiki':
            import tempfile

            from mwlib import nuwiki
            tmpdir = tempfile.mkdtemp()
            nuwiki.extractall(zf, tmpdir)
            res = MultiEnvironment(tmpdir)
            return res
        else:
            raise RuntimeError(f"unknown format {format!r}")

    cp = res.configparser

    if not cp.read(conf):
        raise RuntimeError(f"could not read config file {conf!r}")

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
            raise RuntimeError(f"cannot handle type {t!r} in section {s!r}")

        setattr(res, s, m(**args))

    if not res.wiki:
        raise AttributeError("_makewiki should have set wiki attribute")
    return res


def makewiki(config, metabook=None, **kw):
    res = Environment(metabook) if not config else _makewiki(config, metabook=metabook, **kw)

    if res.wiki:
        res.wiki.env = res
    if res.images:
        res.images.env = res

    res.init_metabook()

    return res
