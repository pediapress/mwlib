#! /usr/bin/env python

# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.

import os
from ConfigParser import ConfigParser
import StringIO

from mwlib import utils, metabook
from mwlib.log import Log

log = Log('mwlib.utils')


def wiki_mwapi(
    base_url=None,
    template_blacklist=None,
    template_exclusion_category=None,
    username=None,
    password=None,
    domain=None,
    script_extension=None,
    **kwargs):
    from mwlib import mwapidb
    return mwapidb.WikiDB(base_url,
        template_blacklist=template_blacklist,
        template_exclusion_category=template_exclusion_category,
        username=username,
        password=password,
        domain=domain,
        script_extension=script_extension,
    )

def wiki_zip(path=None, url=None, name=None, **kwargs):
    from mwlib import zipwiki
    if kwargs:
        log.warn('Unused parameters: %r' % kwargs)
    return zipwiki.Wiki(path)

def wiki_net(articleurl=None, url=None, name=None, imagedescriptionurls=None,
             templateurls=None, templateblacklist=None,
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

def image_mwapi(
    base_url=None,
    username=None,
    password=None,
    domain=None,
    script_extension=None,
    **kwargs
):
    from mwlib import mwapidb
    return mwapidb.ImageDB(base_url,
        username=username,
        password=password,
        domain=domain,
        script_extension=script_extension,
    )

def image_download(url=None, localpath=None, knownlicenses=None, **kwargs):
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

def image_zip(path=None, **kwargs):
    from mwlib import zipwiki
    if kwargs:
        log.warn('Unused parameters: %r' % kwargs)
    return zipwiki.ImageDB(path)



dispatch = dict(
    images = dict(mwapi=image_mwapi, download=image_download, zip=image_zip),
    wiki = dict(mwapi=wiki_mwapi, cdb=wiki_cdb, net=wiki_net, zip=wiki_zip)
)

wpwikis = dict(
    de = 'http://de.wikipedia.org/w/',
    en = 'http://en.wikipedia.org/w/',
    )


class Environment(object):
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
        
    # __getitem__, __setitem__ for compatability (make it look like a dict)
    def __getitem__(self, name):
        if name=='images':
            return self.images
        if name=='wiki':
            return self.wiki
        raise KeyError("Environment.__getitem__ only works for 'wiki' or 'images', not %r" % (name,))
    
    def __setitem__(self, name, val):
        if name=='images':
            self.images = val
        elif name=='wiki':
            self.wiki = val
        else:
            raise KeyError("Environment.__setitem__ only works for 'wiki' or 'images', not %r" % (name,))
    
    def get_licenses(self):
        """Return list of licenses
        
        @returns: list of dicts with license info
        @rtype: [dict]
        """
        
        if 'licenses' not in self.metabook:
            return []
        
        licenses = []
        for license in self.metabook['licenses']:
            wikitext = ''
            
            if license.get('mw_license_url'):
                wikitext = utils.fetch_url(
                    license['mw_license_url'],
                    ignore_errors=True,
                    expected_content_type='text/x-wiki',
                )
                if wikitext:
                    try:
                        wikitext = unicode(wikitext, 'utf-8')
                    except UnicodeError:
                        wikitext = None
            else:
                wikitext = ''
                if license.get('mw_rights_text'):
                    wikitext = license['mw_rights_text']
                if license.get('mw_rights_page'):
                    wikitext += '\n\n[[%s]]' % license['mw_rights_page']
                if license.get('mw_rights_url'):
                    wikitext += '\n\n' + license['mw_rights_url']
            
            if not wikitext:
                continue
            
            licenses.append({
                'title': license.get('name', u'License'),
                'wikitext': wikitext,
            })
        
        return licenses
    

def _makewiki(conf,
    metabook=None,
    username=None, password=None, domain=None,
    script_extension=None,
):
    res = Environment(metabook)
    
    url = None
    if conf.startswith(':'):
        url = wpwikis.get(conf[1:])
    
    if conf.startswith("http://") or conf.startswith("https://"):
        url = conf

    if url:
        res.wiki = wiki_mwapi(url,
            username=username,
            password=password,
            domain=domain,
            script_extension=script_extension,
        )
        res.images = image_mwapi(url,
            username=username,
            password=password,
            domain=domain,
            script_extension=script_extension,
        )
        return res
    
    
    # yes, I really don't want to type this everytime
    wc = os.path.join(conf, "wikiconf.txt")
    if os.path.exists(wc):
        conf = wc 
        
    if conf.lower().endswith(".zip"):
        from mwlib import zipwiki
        res.wiki = zipwiki.Wiki(conf)
        res.images = zipwiki.ImageDB(conf)
        if metabook is None:
            res.metabook = res.wiki.metabook
        return res

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
        
        res[s] = m(**args)
    
    assert res.wiki is not None, '_makewiki should have set wiki attribute'
    return res

def makewiki(conf,
    metabook=None,
    username=None, password=None, domain=None,
    script_extension=None,
):
    res = _makewiki(conf, metabook,
        username=username,
        password=password,
        domain=domain,
        script_extension=script_extension,
    )
    res.wiki.env = res
    if res.images:
        res.images.env = res
    
    try:
        overlaydir = os.environ['MWOVERLAY']
        assert os.path.isdir(overlaydir)
        import mwlib.overlay
        res['wiki'] = mwlib.overlay.OverlayDB(res['wiki'], overlaydir)
    except:
        pass
    return res
