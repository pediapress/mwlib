#! /usr/bin/env py.test
# -*- coding: utf-8 -*-
# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.

from mwlib.advtree import PreFormatted, Text,  buildAdvancedTree, Section, BreakingReturn
from mwlib.dummydb import DummyDB
from mwlib.uparser import parseString
from mwlib import parser
import sys

def _treesanity(r):
    "check that parents match their children"
    for c in r.allchildren():
        if c.parent:
            assert c in c.parent.children
            assert c.parent.children.count(c) == 1
        for cc in c:
            assert cc.parent
            assert cc.parent == c


def test_copy():
    raw = """
===[[Leuchtturm|Leuchttürme]] auf Fehmarn===
*[[Leuchtturm Flügge]] super da
*[[Leuchtturm Marienleuchte]] da auch
*[[Leuchtturm Strukkamphuk]] spitze
*[[Leuchtturm Staberhuk]] supi
*[[Leuchtturm Westermarkelsdorf]]
""".decode("utf8")

    db = DummyDB()
    r = parseString(title="X33", raw=raw, wikidb=db)
    buildAdvancedTree(r)
    c = r.copy()
    _treesanity(c)    
    
    def _check(n1, n2):
        assert n1.caption == n2.caption
        assert n1.__class__ == n2.__class__
        assert len(n1.children) == len(n2.children)
        for i,c1 in enumerate(n1):
            _check(c1, n2.children[i])
    
    _check(r,c)
    

            
def test_removeNewlines():

    # test no action within preformattet
    t = PreFormatted()
    text = u"\t \n\t\n\n  \n\n"
    tn = Text(text)
    t.children.append( tn )
    buildAdvancedTree(t)
    _treesanity(t)
    assert tn.caption == text

    # tests remove node w/ whitespace only if at border
    t = Section()
    tn = Text(text)
    t.children.append( tn )
    buildAdvancedTree(t)
    _treesanity(t)
    #assert tn.caption == u""
    assert not t.children 

    # test remove newlines
    text = u"\t \n\t\n\n KEEP  \n\n"
    t = Section()
    tn = Text(text)
    t.children.append( tn )
    buildAdvancedTree(t)
    _treesanity(t)
    assert tn.caption.count("\n") == 0 
    assert len(tn.caption) == len(text)
    assert t.children 
    

def test_removeBrakingSpaces():
    raw = """
A<br />
B
:C 
<br />D
""".decode("utf8")
    db = DummyDB()
    r = parseString(title="X33", raw=raw, wikidb=db)
    buildAdvancedTree(r)
    _treesanity(r)
    assert len(r.getChildNodesByClass(BreakingReturn)) == 1
    # test copy
    c = r.copy()
    #parser.show(sys.stderr, c, 0)
    _treesanity(c)
    r.appendChild(c)
    
    #parser.show(sys.stderr, r, 0)

    _treesanity(r)
    assert len(r.getChildNodesByClass(BreakingReturn)) == 2
    


