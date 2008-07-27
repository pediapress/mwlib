#! /usr/bin/env python

# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.

"""usable/user parser"""

from mwlib import parser, scanner, expander
from mwlib.log import Log

log = Log('uparser')

def simplify(node, **kwargs):
    "concatenates textnodes in order to reduce the number of objects"
    Text = parser.Text
    
    last = None
    toremove = []
    for i,c in enumerate(node.children):
        if c.__class__ == Text: # would isinstance be safe?
            if last:
                last.caption += c.caption
                toremove.append(i)
            else:
                last = c
        else:
            simplify(c)
            last = None

    for i,ii in enumerate(toremove):
        del node.children[ii-i]

def fixlitags(node, **kwargs):
    Text = parser.Text

    if not isinstance(node, parser.ItemList):
        idx = 0
        while idx < len(node.children):
            if isinstance(node.children[idx], parser.Item):
                lst = parser.ItemList()
                lst.append(node.children[idx])
                node.children[idx] = lst
                idx += 1
                while idx<len(node.children):
                    if isinstance(node.children[idx], parser.Item):
                        lst.append(node.children[idx])
                        del node.children[idx]
                    elif node.children[idx]==Text("\n"):
                        del node.children[idx]
                    else:
                        break                    
            else:
                idx += 1

    for x in node.children:
        fixlitags(x)

def removeBoilerplate(node, **kwargs):
    i = 0
    while i < len(node.children):
        x = node.children[i]
        if isinstance(x, parser.TagNode) and x.caption=='div':
            try:
                klass = x.values.get('class', '')
            except AttributeError:
                klass = ''
                
            if 'boilerplate' in klass:
                del node.children[i]
                continue
            
        i += 1

    for x in node.children:
        removeBoilerplate(x)


def addurls(node, title=None, revision=None, wikidb=None, **kwargs):
    """Add 'url' attribute to Link nodes with full HTTP URL to the target"""
    
    if wikidb is None or title is None:
        return
    if not hasattr(wikidb, 'getLinkURL'):
        return
    if isinstance(node, parser.Link) and not isinstance(node, parser.ImageLink):
        node.url = wikidb.getLinkURL(node, title, revision=revision)
    for x in node.children:
        addurls(x, title=title, revision=revision, wikidb=wikidb)

postprocessors = [removeBoilerplate, simplify, fixlitags, addurls]

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
    
    tokens = scanner.tokenize(input, title)

    a = parser.Parser(tokens, title, lang=lang, interwikimap=interwikimap).parse()
    a.caption = title
    for x in postprocessors:
        x(a, title=title, revision=revision, wikidb=wikidb, lang=lang)
    
    return a


def simpleparse(raw):    # !!! USE FOR DEBUGGING ONLY !!! does not use post processors
    import sys
    from mwlib import dummydb
    db = dummydb.DummyDB()
    
    tokens = scanner.tokenize(raw)
    r=parser.Parser(tokens, "unknown").parse()
    parser.show(sys.stdout, r, 0)
    return r

def main():
    from mwlib.dummydb import DummyDB

    import os
    import sys
    
    db = DummyDB()
    
    for x in sys.argv[1:]:
        input = unicode(open(x).read(), 'utf8')
        title = unicode(os.path.basename(x))
        parseString(title, input, db)

if __name__=="__main__":
    main()

