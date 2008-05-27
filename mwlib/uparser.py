#! /usr/bin/env python

# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.

"""usable/user parser"""

from mwlib import parser, scanner, expander

def simplify(node):
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

def fixlitags(node):
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

def removeBoilerplate(node):
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
        
            
        

postprocessors = [removeBoilerplate, simplify, fixlitags]

def parseString(title=None, raw=None, wikidb=None, revision=None):
    """parse article with title from raw mediawiki text"""
    assert title is not None 

    if raw is None:
        raw = wikidb.getRawArticle(title, revision=revision)
        assert raw is not None, "cannot get article %r" % (title,)
    if wikidb:
        te = expander.Expander(raw, pagename=title, wikidb=wikidb)
        input = te.expandTemplates()
    else:
        input = raw

    tokens = scanner.tokenize(input, title)

    a = parser.Parser(tokens, title).parse()
    a.caption = title
    for x in postprocessors:
        x(a)
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

