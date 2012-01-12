#! /usr/bin/env py.test
# -*- coding: utf-8 -*-
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

import sys
import os

from mwlib.advtree import (
    PreFormatted, Text,  buildAdvancedTree, Section, BreakingReturn,  _idIndex,
    Indented, DefinitionList, DefinitionTerm, DefinitionDescription, Item, Cell, Span, Row, ImageLink
)
from mwlib.dummydb import DummyDB
from mwlib.uparser import parseString
from mwlib import parser
from mwlib.xfail import xfail


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
        for i, c1 in enumerate(n1):
            _check(c1, n2.children[i])

    _check(r, c)


def test_removeNewlines():

    # test no action within preformattet
    t = PreFormatted()
    text = u"\t \n\t\n\n  \n\n"
    tn = Text(text)
    t.children.append(tn)
    buildAdvancedTree(t)
    _treesanity(t)
    assert tn.caption == text

    # tests remove node w/ whitespace only if at border
    t = Section()
    tn = Text(text)
    t.children.append(tn)
    buildAdvancedTree(t)
    _treesanity(t)
    #assert tn.caption == u""
    assert not t.children

    # test remove newlines
    text = u"\t \n\t\n\n KEEP  \n\n"
    t = Section()
    tn = Text(text)
    t.children.append(tn)
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
    for i, br in enumerate(brs):
        assert br in br.siblings
        assert i == _idIndex(br.parent.children, br)
        assert len([x for x in br.parent.children if x is not br]) == len(brs) - 1
        for bbr in brs:
            if br is bbr:
                continue
            assert br == bbr
            assert br is not bbr


# FIXME isNavBox removed from advtree. could be implemented in general treecleaner - move test there
## def test_isnavbox():
##     raw = """
## == test ==
## <div class="noprint">
## some text
## </div>
## """.decode("utf8")
##     db = DummyDB()
##     r = parseString(title="X33", raw=raw, wikidb=db)
##     buildAdvancedTree(r)
##     assert 1 == len([c for c in r.getAllChildren() if c.isNavBox()])
def test_definitiondescription():
    raw = u"""
== test ==

:One
::Two
:::Three
::::Four

"""
    db = DummyDB()
    r = parseString(title="t", raw=raw, wikidb=db)
    parser.show(sys.stdout, r)

    buildAdvancedTree(r)
    dd = r.getChildNodesByClass(DefinitionDescription)
    print "DD:", dd
    for c in dd:
        assert c.indentlevel == 1
    assert len(dd) == 4


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
    raw = '''<table><tr><td colspan="bogus">no colspan </td></tr></table>'''
    r = parseString(title='t', raw=raw)
    buildAdvancedTree(r)
    assert r.getChildNodesByClass(Cell)[0].colspan is 1

    raw = '''<table><tr><td colspan="-1">no colspan </td></tr></table>'''
    r = parseString(title='t', raw=raw)
    buildAdvancedTree(r)
    assert r.getChildNodesByClass(Cell)[0].colspan is 1

    raw = '''<table><tr><td colspan="2">colspan1</td></tr></table>'''
    r = parseString(title='t', raw=raw)
    buildAdvancedTree(r)
    assert r.getChildNodesByClass(Cell)[0].colspan is 2


def test_attributes():
    t1 = '''
{|
|- STYLE="BACKGROUND:#FFDEAD;"
|stuff
|}
'''
    r = parseString(title='t', raw=t1)
    buildAdvancedTree(r)
    n = r.getChildNodesByClass(Row)[0]
    print n.attributes, n.style
    assert isinstance(n.style, dict)
    assert isinstance(n.attributes, dict)
    assert n.style["background"] == "#FFDEAD"


def getAdvTree(raw):
    tree = parseString(title='test', raw=raw)
    buildAdvancedTree(tree)
    return tree


def test_img_no_caption():
    raw = u'''[[Image:Chicken.jpg|image caption]]

[[Image:Chicken.jpg|none|image caption: align none]]

[[Image:Chicken.jpg|none|200px|image caption: align none, 200px]]

[[Image:Chicken.jpg|frameless|image caption frameless]]

[[Image:Chicken.jpg|none|200px|align none, 200px]]

<gallery perrow="2">
Image:Luna-16.jpg
Image:Lunokhod 1.jpg
Image:Voyager.jpg
Image:Cassini Saturn Orbit Insertion.jpg|
</gallery>
'''

    tree = getAdvTree(raw)
    images = tree.getChildNodesByClass(ImageLink)
    assert len(images) == 9
    for image in images:
        assert image.render_caption == False


def test_img_has_caption():
    raw = u'''[[Image:Chicken.jpg|thumb|image caption thumb]]

[[Image:Chicken.jpg|framed|image caption framed]]

[[Image:Chicken.jpg|none|thumb|align none, thumb]]

<gallery perrow="2">
Image:Luna-16.jpg|''[[Luna 16]]''<br>First unmanned lunar sample return
Image:Lunokhod 1.jpg|''[[Lunokhod 1]]''<br>First lunar rover
Image:Voyager.jpg|''[[Voyager 2]]''<br>First Uranus flyby<br>First Neptune flyby
Image:Cassini Saturn Orbit Insertion.jpg|''[[Cassini–Huygens]]''<br>First Saturn orbiter
</gallery>

[[Image:Horton Erythromelalgia 1939.png|center|600px|<div align="center">"Erythromelalgia of the head", Horton&nbsp;1939<ref name="BTH39"/></div>|frame]]

[[Image:Anatomie1.jpg|thumb|none|500px|Bild der anatomischen Verhältnisse. In Rot die Hauptschlagader (Carotis).]]
'''

    tree = getAdvTree(raw)
    images = tree.getChildNodesByClass(ImageLink)
    assert len(images) == 9
    for image in images:
        assert image.render_caption == True
