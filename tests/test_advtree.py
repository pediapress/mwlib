#! /usr/bin/env py.test
# -*- coding: utf-8 -*-
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
    

def test_removeBrakingSpaces():
    raw = """== Geschichte ==

'''1938''' Umbenennung von ''Das Goldene Zeitalter'' in ''Trost'' (deutsche Ausgabe)<br />
'''1939''' fragte die Zeitschrift 
:''„Wie ist es möglich, Stillschweigen zu bewahren über Greueltaten in einem Land wie Deutschland, wo auf einen Schlag 40.000 unschuldige Menschen verhaftet und in einer einzigen Nacht 70 von ihnen in einem Gefängnis hingerichtet werden, ... wo jedes Heim, jede Einrichtung und jedes Krankenhaus für die Alten, die Armen und die Hilflosen sowie jedes Waisenhaus zerstört wird?“''
:Die Zeugen Jehovas sehen sich damit als frühe Ankläger des NS-Regimes, lange bevor die Folgen des Nationalsozialismus 1944-45 der Weltöffentlichkeit durch Fotos und Filme der Wochenschauen vermittelt wurden.
<br />'''1946''' Umbenennung von ''Consolation'' in ''Awake!'' (englische Ausgabe)
<br />'''1947''' Umbenennung von ''Trost'' in ''Erwachet!'' (deutsche Ausgabe)
""".decode("utf8")
    from mwlib.dummydb import DummyDB
    from mwlib.uparser import parseString
    from mwlib.parser import show
    import sys
    db = DummyDB()
    r = parseString(title="X33", raw=raw, wikidb=db)
    buildAdvancedTree(r)
    print "yes"
    show(sys.stderr, r, 0)


