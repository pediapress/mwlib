#! /usr/bin/env python

# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.

import os
from ConfigParser import ConfigParser

def wiki_mwapi(base_url=None, license=None, template_blacklist=None):
    from mwlib import mwapidb
    return mwapidb.WikiDB(base_url, license, template_blacklist)

def wiki_zip(path=None, url=None, name=None):
    from mwlib import zipwiki
    return zipwiki.Wiki(path)

def wiki_net(articleurl=None, url=None, name=None, imagedescriptionurls=None,
             templateurls=None, templateblacklist=None, defaultarticlelicense=None,
             defaultauthors=None, **kwargs):
    from mwlib import netdb
    
    if templateurls:
        templateurls = [x for x in templateurls.split() if x]
    else:
        raise RuntimeError("templateurls parameter for netdb not set in [wiki] section")
    
    if imagedescriptionurls:
        imagedescriptionurls = [x for x in imagedescriptionurls.split() if x]
    else:
        raise RuntimeError("imagedescriptionurls parameter for netdb not set in [wiki] section")
    
    if defaultauthors:
        defaultauthors = [a.strip() for a in defaultauthors.split(',')]
    
    return netdb.NetDB(articleurl,
        imagedescriptionurls=imagedescriptionurls,
        templateurls=templateurls,
        templateblacklist=templateblacklist,
        defaultauthors=defaultauthors,
    )

def wiki_cdb(path=None, **kwargs):
    from mwlib import cdbwiki
    path = os.path.expanduser(path)
    db=cdbwiki.WikiDB(path)
    return db

def image_mwapi(base_url=None, shared_base_url=None):
    from mwlib import mwapidb
    return mwapidb.ImageDB(base_url, shared_base_url)

def image_download(url=None, localpath=None, knownlicenses=None):
    assert url, "must supply url in [images] section"
    from mwlib import netdb

    if localpath:
        localpath = os.path.expanduser(localpath)
    urls = [x for x in url.split() if x]
    assert urls
    
    if knownlicenses:
        knownlicenses = [x for x in knownlicenses.split() if x]
    else:
        knownlicenses = None
    
    imgdb = netdb.ImageDB(urls, cachedir=localpath, knownLicenses=knownlicenses)
    return imgdb

def image_zip(path=None):
    from mwlib import zipwiki
    return zipwiki.ImageDB(path)



dispatch = dict(
    images = dict(mwapi=image_mwapi, download=image_download, zip=image_zip),
    wiki = dict(mwapi=wiki_mwapi, cdb=wiki_cdb, net=wiki_net, zip=wiki_zip)
)

def _makewiki(conf):
    res = {}

    # yes, I really don't want to type this everytime
    wc = os.path.join(conf, "wikiconf.txt")
    if os.path.exists(wc):
        conf = wc 

    if conf.startswith("http://") or conf.startswith("https://"):
        res['wiki'] = wiki_mwapi(conf)
        res['images'] = image_mwapi(conf)
        return res
    
            
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
    return res

def makewiki(conf):
    res = _makewiki(conf)
    
    try:
        overlaydir = os.environ['MWOVERLAY']
        assert os.path.isdir(overlaydir)
        import mwlib.overlay
        res['wiki'] = mwlib.overlay.OverlayDB(res['wiki'], overlaydir)
    except:
        pass
    return res
