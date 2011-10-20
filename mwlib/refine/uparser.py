
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

from mwlib import expander, nshandling, metabook
from mwlib.log import Log
from mwlib.refine import core, compat

log = Log('refine.uparser')

def parseString(
    title=None,
    raw=None,
    wikidb=None,
    revision=None,
    lang=None,
    magicwords=None
):
    """parse article with title from raw mediawiki text"""

    uniquifier = None
    siteinfo = None
    assert title is not None, 'no title given'
    if raw is None:
        page = wikidb.normalize_and_get_page(title, 0)
        if page:
            raw = page.rawtext
        else:
            raw = None
        
        assert raw is not None, "cannot get article %r" % (title,)
    if wikidb:
        te = expander.Expander(raw, pagename=title, wikidb=wikidb)
        input = te.expandTemplates(True)
        uniquifier = te.uniquifier

        if hasattr(wikidb, 'get_siteinfo'):
            siteinfo = wikidb.get_siteinfo()

        src = None 
        if hasattr(wikidb, 'getSource'):
            src = wikidb.getSource(title, revision=revision)
            assert not isinstance(src, dict)
            
        if not src:
            src=metabook.source()
            
        if lang is None:
            lang = src.language
        if magicwords is None:
            if siteinfo is not None and 'magicwords' in siteinfo:
                magicwords = siteinfo['magicwords']
            else:
                magicwords = src.get('magicwords')
    else:
        input = raw
        te = None
        
    if siteinfo is None:
        nshandler = nshandling.get_nshandler_for_lang(lang)
    else:
        nshandler = nshandling.nshandler(siteinfo)
    a = compat.parse_txt(input, title=title, wikidb=wikidb, nshandler=nshandler, lang=lang, magicwords=magicwords, uniquifier=uniquifier, expander=te)
    
    a.caption = title
    if te and te.magic_displaytitle:
        a.caption = te.magic_displaytitle
        
    from mwlib.old_uparser import postprocessors
    for x in postprocessors:
        x(a, title=title, revision=revision, wikidb=wikidb, lang=lang)
    
    return a

def simpleparse(raw,lang=None):    # !!! USE FOR DEBUGGING ONLY !!! does not use post processors
    a=compat.parse_txt(raw,lang=lang)
    core.show(a)    
    return a
