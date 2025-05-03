#! /usr/bin/env py.test
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

import sys

import pytest

from mwlib import parser
from mwlib.parser.advtree import (
    BreakingReturn,
    Cell,
    DefinitionDescription,
    DefinitionList,
    DefinitionTerm,
    ImageLink,
    Item,
    PreFormatted,
    Row,
    Section,
    Text,
    _id_index,
    build_advanced_tree,
)
from mwlib.parser.dummydb import DummyDB
from mwlib.parser.refine.uparser import parse_string


def _treesanity(r):
    """check that parents match their children"""
    for c in r.allchildren():
        if c.parent:
            assert c in c.parent.children
            assert _id_index(c.parent.children, c) >= 0
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
"""

    db = DummyDB()
    r = parse_string(title="X33", raw=raw, wikidb=db)
    build_advanced_tree(r)
    c = r.copy()
    _treesanity(c)

    def _check(n1, n2):
        assert n1.caption == n2.caption
        assert n1.__class__ == n2.__class__
        assert len(n1.children) == len(n2.children)
        for i, c1 in enumerate(n1):
            _check(c1, n2.children[i])

    _check(r, c)


def test_remove_newlines():
    # test no action within preformattet
    t = PreFormatted()
    text = "\t \n\t\n\n  \n\n"
    tn = Text(text)
    t.children.append(tn)
    build_advanced_tree(t)
    _treesanity(t)
    assert tn.caption == text

    # tests remove node w/ whitespace only if at border
    t = Section()
    tn = Text(text)
    t.children.append(tn)
    build_advanced_tree(t)
    _treesanity(t)
    assert not t.children

    # test remove newlines
    text = "\t \n\t\n\n KEEP  \n\n"
    t = Section()
    tn = Text(text)
    t.children.append(tn)
    build_advanced_tree(t)
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
"""

    db = DummyDB()
    r = parse_string(title="X33", raw=raw, wikidb=db)
    build_advanced_tree(r)
    _treesanity(r)

    brs = r.get_child_nodes_by_class(BreakingReturn)
    for i, br in enumerate(brs):
        assert br in br.siblings
        assert i == _id_index(br.parent.children, br)
        assert len([x for x in br.parent.children if x is not br]) == len(brs) - 1
        for bbr in brs:
            if br is bbr:
                continue
            assert br == bbr
            assert br is not bbr


def test_definitiondescription():
    raw = """
== test ==

:One
::Two
:::Three
::::Four

"""
    db = DummyDB()
    r = parse_string(title="t", raw=raw, wikidb=db)
    parser.show(sys.stdout, r)

    build_advanced_tree(r)
    dd = r.get_child_nodes_by_class(DefinitionDescription)
    print("DD:", dd)
    for c in dd:
        assert c.indentlevel == 1
    assert len(dd) == 4


@pytest.mark.xfail
def test_definition_list():
    """http://code.pediapress.com/wiki/ticket/221"""
    raw = """
;termA
:descr1
"""
    r = parse_string(title="t", raw=raw)
    build_advanced_tree(r)
    dls = r.get_child_nodes_by_class(DefinitionList)
    assert len(dls) == 1
    assert dls[0].get_child_nodes_by_class(DefinitionTerm)
    assert dls[0].get_child_nodes_by_class(DefinitionDescription)
    raw = raw.replace("\n", "")


def test_ulist():
    """http://code.pediapress.com/wiki/ticket/222"""
    raw = """
* A item
*: B Previous item continues.
"""
    r = parse_string(title="t", raw=raw)
    build_advanced_tree(r)
    #    parser.show(sys.stdout, r)
    assert len(r.get_child_nodes_by_class(Item)) == 1


def test_colspan():
    raw = """<table><tr><td colspan="bogus">no colspan </td></tr></table>"""
    r = parse_string(title="t", raw=raw)
    build_advanced_tree(r)
    assert r.get_child_nodes_by_class(Cell)[0].colspan == 1

    raw = """<table><tr><td colspan="-1">no colspan </td></tr></table>"""
    r = parse_string(title="t", raw=raw)
    build_advanced_tree(r)
    assert r.get_child_nodes_by_class(Cell)[0].colspan == 1

    raw = """<table><tr><td colspan="2">colspan1</td></tr></table>"""
    r = parse_string(title="t", raw=raw)
    build_advanced_tree(r)
    assert r.get_child_nodes_by_class(Cell)[0].colspan == 2


def test_attributes():
    t1 = """
{|
|- STYLE="BACKGROUND:#FFDEAD;"
|stuff
|}
"""
    r = parse_string(title="t", raw=t1)
    build_advanced_tree(r)
    n = r.get_child_nodes_by_class(Row)[0]
    print(n.attributes, n.style)
    assert isinstance(n.style, dict)
    assert isinstance(n.attributes, dict)
    assert n.style["background"] == "#FFDEAD"


def get_adv_tree(raw):
    tree = parse_string(title="test", raw=raw)
    build_advanced_tree(tree)
    return tree


def test_img_no_caption():
    raw = """[[Image:Chicken.jpg|image caption]]

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
"""

    tree = get_adv_tree(raw)
    images = tree.get_child_nodes_by_class(ImageLink)
    assert len(images) == 9
    for image in images:
        assert image.render_caption is False


def test_img_has_caption():
    raw = """[[Image:Chicken.jpg|thumb|image caption thumb]]

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
"""

    tree = get_adv_tree(raw)
    images = tree.get_child_nodes_by_class(ImageLink)
    assert len(images) == 9
    for image in images:
        assert image.render_caption is True
