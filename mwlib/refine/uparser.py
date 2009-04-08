
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.txt for additional licensing information.

from mwlib import expander
from mwlib.log import Log
from mwlib.refine import core, compat

log = Log('refine.uparser')

def parseString(
    title=None,
    raw=None,
    wikidb=None,
    revision=None,
    lang=None,
    interwikimap=None,
    magicwords=None
):
    """parse article with title from raw mediawiki text"""

    uniquifier = None
    assert title is not None, 'no title given'
    if raw is None:
        raw = wikidb.getRawArticle(title, revision=revision)
        assert raw is not None, "cannot get article %r" % (title,)
    if wikidb:
        te = expander.Expander(raw, pagename=title, wikidb=wikidb)
        input = te.expandTemplates(True)
        uniquifier = te.uniquifier
        
        if hasattr(wikidb, 'getSource'):
            src = wikidb.getSource(title, revision=revision)
            if not src:
                src = {} # this can happen for the license article
        else:
            src={}
            
        if lang is None:
            lang = src.get('language')
        if magicwords is None:
            magicwords = src.get('magicwords')
        
        if interwikimap is None and hasattr(wikidb, 'getInterwikiMap'):
            interwikimap = wikidb.getInterwikiMap(title, revision=revision)
    else:
        input = raw
        te = None
        
    a = compat.parse_txt(input, lang=lang, interwikimap=interwikimap, magicwords=magicwords, uniquifier=uniquifier, expander=te)
    
    a.caption = title
    from mwlib.old_uparser import postprocessors
    for x in postprocessors:
        x(a, title=title, revision=revision, wikidb=wikidb, lang=lang)
    
    return a

def simpleparse(raw):    # !!! USE FOR DEBUGGING ONLY !!! does not use post processors
    a=compat.parse_txt(raw)
    core.show(a)    
    return a
