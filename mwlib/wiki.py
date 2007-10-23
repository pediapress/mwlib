#! /usr/bin/env python

# Copyright (c) 2007, PediaPress GmbH
# See README.txt for additional licensing information.

import os
from ConfigParser import ConfigParser

def wiki_zip(path=None, url=None, name=None):
    from mwlib import zipwiki
    return zipwiki.Wiki(path)

def wiki_net(articleurl=None, url=None, name=None):
    from mwlib import netdb
    return netdb.NetDB(articleurl)

def wiki_cdb(path=None):
    from mwlib import cdbwiki
    path = os.path.expanduser(path)
    db=cdbwiki.WikiDB(path)
    return db

def image_download(url=None, localpath=None):
    assert url, "must supply url in [images] section"
    from mwlib import netdb

    if localpath:
        localpath = os.path.expanduser(localpath)
    urls = [x for x in url.split() if x]
    assert urls
    
    imgdb = netdb.ImageDB(urls, localpath=localpath)
    return imgdb

def image_zip(path=None):
    from mwlib import zipwiki
    return zipwiki.ImageDB(path)



dispatch = dict(
    images = dict(download=image_download, zip=image_zip),
    wiki = dict(cdb=wiki_cdb, net=wiki_net, zip=wiki_zip)
)

def makewiki(conf):
    res = {}

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
    try:
        overlaydir = os.environ['MWOVERLAY']
        assert os.path.isdir(overlaydir)
        import mwlib.overlay
        res['wiki'] = mwlib.overlay.OverlayDB(res['wiki'], overlaydir)
    except:
        pass
    return res
