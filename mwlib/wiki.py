#! /usr/bin/env python

# Copyright (c) 2007, PediaPress GmbH
# See README.txt for additional licensing information.

import os
from ConfigParser import ConfigParser

def wiki_zip(path=None, url=None, name=None):
    from mwlib import zipwiki
    return zipwiki.Wiki(path)

def wiki_net(articleurl=None, url=None, name=None, templateurls=None, templateblacklist=None):
    from mwlib import netdb
    if templateurls:
        templateurls = [x for x in templateurls.split() if x]
    else:
        raise RuntimeError("templateurls parameter for netdb not set in [wiki] section")
    return netdb.NetDB(articleurl, templateurls=templateurls, templateblacklist=templateblacklist)

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
    
    imgdb = netdb.ImageDB(urls, cachedir=localpath)
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

    # yes, I really don't want to type this everytime
    wc = os.path.join(conf, "wikiconf.txt")
    if os.path.exists(wc):
        conf = wc 

    if conf.lower().endswith(".zip"):
        from mwlib import zipwiki
        res['wiki'] = zipwiki.Wiki(conf)
        res['images'] = zipwiki.ImageDB(conf)
        return res

    cp=ConfigParser()

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
