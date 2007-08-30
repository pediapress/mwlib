#! /usr/bin/env python

# Copyright (c) 2007, pediapress GMBH
# See README.txt for additional licensing information.

import os
from ConfigParser import ConfigParser

def wiki_net(url=None):
    from mwlib import netdb
    return netdb.NetDB(url)

def wiki_cdb(path=None):
    from mwlib import cdbwiki
    path = os.path.expanduser(path)
    db=cdbwiki.WikiDB(path)
    return db

def image_download(url=None, localpath=None):
    assert url and localpath, "must supply url and localpath in [images] section"
    from mwlib import netdb

    localpath = os.path.expanduser(localpath)
    urls = [x for x in url.split() if x]
    assert urls
    
    imgdb = netdb.ImageDB(urls, localpath)
    return imgdb



dispatch = dict(
    images = dict(download = image_download),
    wiki = dict(cdb=wiki_cdb, net=wiki_net)
)

def makewiki(conf):
    res = {}

    wc = os.path.join(conf, "wikiconf.txt")
    if os.path.exists(wc):
        conf = wc
    
    if conf.lower().endswith(".zip"):
        from mwlib import zipwiki
        res['wiki'] = zipwiki.Wiki(conf)
        res['images'] = zipwiki.ImageDB(conf)
        return res

    
    cp=ConfigParser()
    cp.read(conf)

    
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
        
        res[s] = m(**args)

    assert "wiki" in res
    return res
