#! /usr/bin/env py.test
# -*- coding: utf-8 -*-
# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.

from mwlib.advtree import PreFormatted, Text,  buildAdvancedTree, Section, BreakingReturn


def test_removeNewlines():

    # test no action within preformattet
    t = PreFormatted()
    text = u"\t \n\t\n\n  \n\n"
    tn = Text(text)
    t.children.append( tn )
    buildAdvancedTree(t)
    assert tn.caption == text

    # tests remove node w/ whitespace only if at border
    t = Section()
    tn = Text(text)
    t.children.append( tn )
    buildAdvancedTree(t)
    #assert tn.caption == u""
    assert not t.children 

    # test remove newlines
    text = u"\t \n\t\n\n KEEP  \n\n"
    t = Section()
    tn = Text(text)
    t.children.append( tn )
    buildAdvancedTree(t)
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
    from mwlib.dummydb import DummyDB
    from mwlib.uparser import parseString
    from mwlib.parser import show
    import sys
    db = DummyDB()
    r = parseString(title="X33", raw=raw, wikidb=db)
    buildAdvancedTree(r)
    assert len(r.getChildNodesByClass(BreakingReturn)) == 1


