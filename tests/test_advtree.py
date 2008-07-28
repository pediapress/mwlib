#! /usr/bin/env py.test
# -*- coding: utf-8 -*-
# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.

from mwlib.advtree import (
    PreFormatted, Text,  buildAdvancedTree, Section, BreakingReturn,  _idIndex,
    Indented, DefinitionList, DefinitionTerm, DefinitionDescription, Item, Cell
)
from mwlib.dummydb import DummyDB
from mwlib.uparser import parseString
from mwlib import parser
from mwlib.xfail import xfail

import sys

def _treesanity(r):
    "check that parents match their children"
    for c in r.allchildren():
        if c.parent:
            assert c in c.parent.children
            assert _idIndex(c.parent.children, c) >= 0
        for cc in c:
            assert cc.parent
            assert cc.parent is c


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
    


def test_identity():
    raw = """
<br/>
<br/>
<br/>
<br/>
<br/>
<br/>
<br/>
<br/>
""".decode("utf8")

    db = DummyDB()
    r = parseString(title="X33", raw=raw, wikidb=db)
    buildAdvancedTree(r)
    _treesanity(r)    
    
    brs = r.getChildNodesByClass(BreakingReturn)
    for i,br in enumerate(brs):
        assert br in br.siblings
        assert i == _idIndex(br.parent.children, br)
        assert len([x for x in br.parent.children if x is not br]) == len(brs)-1
        for bbr in brs:
            if br is bbr:
                continue
            assert br == bbr
            assert br is not bbr
            
            
def test_isnavbox():
    raw = """
== test ==

<div class="noprint">
some text
</div>
""".decode("utf8")

    db = DummyDB()
    r = parseString(title="X33", raw=raw, wikidb=db)
    buildAdvancedTree(r)
    assert 1 == len([c for c in r.getAllChildren() if c.isNavBox()])


def test_indentation():
    raw = u"""
== test ==

:One
::Two
:::Three
::::Four

"""
    db = DummyDB()
    r = parseString(title="t", raw=raw, wikidb=db)
    buildAdvancedTree(r)
    for i,c in enumerate(r.getChildNodesByClass(Indented)):
        assert c.indentlevel == i + 1
    assert i == 3


@xfail
def test_defintion_list():
    """http://code.pediapress.com/wiki/ticket/221"""
    raw = u''';termA
:descr1
'''

    for i in range(2):
        r = parseString(title='t', raw=raw)
        buildAdvancedTree(r)
        dls = r.getChildNodesByClass(DefinitionList)
        assert len(dls) == 1
        assert dls[0].getChildNodesByClass(DefinitionTerm)
        assert dls[0].getChildNodesByClass(DefinitionDescription)
        raw = raw.replace('\n', '')


@xfail
def test_ulist():
    """http://code.pediapress.com/wiki/ticket/222"""
    raw = u"""
* A item
*: B Previous item continues.
"""
    r = parseString(title='t', raw=raw)
    buildAdvancedTree(r)
#    parser.show(sys.stdout, r)
    assert len(r.getChildNodesByClass(Item)) == 1


def test_colspan():
    t1 = '''<table><tr><td colspan="one">no colspan </td></tr></table>'''
    r = parseString(title='t', raw=t1)
    buildAdvancedTree(r)
    parser.show(sys.stdout, r)
    assert r.getChildNodesByClass(Cell)[0].colspan is None

    t1 = '''<table><tr><td colspan="2">colspan1</td></tr></table>'''
    r = parseString(title='t', raw=t1)
    buildAdvancedTree(r)
    parser.show(sys.stdout, r)
    assert r.getChildNodesByClass(Cell)[0].colspan is 2
    
