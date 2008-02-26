#! /usr/bin/env py.test
# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.
from mwlib.advtree import PreFormatted, Text,  buildAdvancedTree, Section


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


    
    
