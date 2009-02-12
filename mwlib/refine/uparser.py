
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
):
    """parse article with title from raw mediawiki text"""
    
    assert title is not None, 'no title given'
    
    if raw is None:
        raw = wikidb.getRawArticle(title, revision=revision)
        assert raw is not None, "cannot get article %r" % (title,)
    if wikidb:
        te = expander.Expander(raw, pagename=title, wikidb=wikidb)
        input = te.expandTemplates()
        if lang is None and hasattr(wikidb, 'getSource'):
            src = wikidb.getSource(title, revision=revision)
            if src:
                lang = src.get('language')
        if interwikimap is None and hasattr(wikidb, 'getInterwikiMap'):
            interwikimap = wikidb.getInterwikiMap(title, revision=revision)
    else:
        input = raw

    a = compat.parse_txt(input, lang=lang, interwikimap=interwikimap)
    
#     tokens = utoken.tokenize(input, title)

#     a = parser.Parser(tokens, title, lang=lang, interwikimap=interwikimap).parse()
    a.caption = title
#     for x in postprocessors:
#         x(a, title=title, revision=revision, wikidb=wikidb, lang=lang)
    
    return a


def simpleparse(raw):    # !!! USE FOR DEBUGGING ONLY !!! does not use post processors
    from mwlib import dummydb
    db = dummydb.DummyDB()

    a=compat.parse_txt(raw)
    core.show(a)    
    return a
    
        
#     tokens = scanner.tokenize(raw)
#     r=parser.Parser(tokens, "unknown").parse()
#     parser.show(sys.stdout, r, 0)
#     return r
