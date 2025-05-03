#! /usr/bin/env py.test
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

import sys

import pytest

from mwlib import parser
from mwlib.parser import LangLink
from mwlib.parser.advtree import (
    BreakingReturn,
    Center,
    DefinitionDescription,
    Div,
    Emphasized,
    Gallery,
    ItemList,
    Paragraph,
    PreFormatted,
    Reference,
    Row,
    Section,
    Strong,
    Table,
    Text,
    Underline,
    build_advanced_tree,
)
from mwlib.parser.dummydb import DummyDB
from mwlib.parser.refine.uparser import parse_string
from mwlib.parser.treecleaner import TreeCleaner


def _treesanity(r):
    "check that parents match their children"
    for c in r.allchildren():
        if c.parent:
            assert c in c.parent.children
            assert len([x for x in c.parent.children if x is c]) == 1
        for cc in c:
            assert cc.parent
            assert cc.parent is c


def get_tree_from_markup(raw):
    return parse_string(title="Test", raw=raw, wikidb=DummyDB())


def clean_markup(raw):
    print(f"Parsing {raw!r}")

    tree = get_tree_from_markup(raw)

    print("before treecleaner: >>>")
    show_tree(tree)
    print("<<<")

    print("=" * 20)
    build_advanced_tree(tree)
    tc = TreeCleaner(tree, save_reports=True)
    tc.clean_all(skip_methods=[])
    reports = tc.get_reports()
    print("after treecleaner: >>>")
    show_tree(tree)
    print("<<<")
    return (tree, reports)


def clean_markup_single(raw, cleaner_method):
    tree = get_tree_from_markup(raw)
    build_advanced_tree(tree)
    tc = TreeCleaner(tree, save_reports=True)
    tc.clean([cleaner_method])
    reports = tc.get_reports()
    return (tree, reports)


def show_tree(tree):
    parser.show(sys.stdout, tree, 0)


def test_fix_lists():
    raw = r"""
para

* list item 1
* list item 2
** list item 2.1
* list item 3

* list 2 item 1
* list 2 item 2

para

* list 3
"""
    tree, _ = clean_markup(raw)
    lists = tree.get_child_nodes_by_class(ItemList)
    for li in lists:
        print(li, li.get_parents())
        assert all(p.__class__ != Paragraph for p in li.get_parents())
    _treesanity(tree)


def test_fix_lists2():
    raw = r"""
* list item 1
* list item 2
some text in the same paragraph

another paragraph
    """
    # cleaner should do nothing
    tree, _ = clean_markup(raw)
    lists = tree.get_child_nodes_by_class(ItemList)
    li = lists[0]
    assert li.parent.__class__ == Paragraph
    txt = "".join([x.as_text() for x in li.siblings])
    assert "some text in the same paragraph" in txt
    assert "another" not in txt


def test_fix_lists3():
    raw = r"""
* ul1
* ul2
# ol1
# ol2
"""
    tree, reports = clean_markup(raw)
    assert len(tree.children) == 2  # 2 itemlists as only children of article
    assert all(c.__class__ == ItemList for c in tree.children)


def test_childless_nodes():
    raw = r"""
blub

<source></source>

*

<div></div>

<u></u>
    """
    tree, reports = clean_markup(raw)
    assert len(tree.children) == 1  # assert only the 'blub' paragraph is left and the rest removed
    assert tree.children[0].__class__ == Paragraph


def test_remove_lang_links():
    raw = r"""
bla
[[de:Blub]]
[[en:Blub]]
[[es:Blub]]
blub
"""
    tree, reports = clean_markup(raw)
    show_tree(tree)
    langlinks = tree.find(LangLink)
    assert not langlinks, "expected no LangLink instances"


def test_remove_critical_tables():
    raw = r"""
{| class="navbox"
|-
| bla
| blub
|}

blub
"""
    tree, reports = clean_markup(raw)
    assert len(tree.get_child_nodes_by_class(Table)) == 0


def test_fix_table_colspans():
    raw = r"""
{|
|-
| colspan="5" | bla
|-
| bla
| blub
|}
    """
    tree, reports = clean_markup(raw)
    t = tree.get_child_nodes_by_class(Table)[0]
    cell = t.children[0].children[0]
    assert cell.colspan == 2


def test_fix_table_colspans2():
    """http://es.wikipedia.org/w/index.php?title=Rep%C3%BAblica_Dominicana&oldid=36394218"""
    raw = r"""
{|
|-
| colspan="2" | bla1
|-
| colspan="3" | bla2

|}
    """
    tree, reports = clean_markup(raw)
    t = tree.get_child_nodes_by_class(Table)[0]
    cell = t.children[0].children[0]
    show_tree(t)
    assert cell.colspan == 1


# test changed after 3258e2f7978fc4592567bb64977ba5404ee949da


def test_fix_table_colspans3():
    """http://es.wikipedia.org/w/index.php?title=Rep%C3%BAblica_Dominicana&oldid=36394218"""
    raw = r"""
{| cellpadding="0" cellspacing="0" border="0" style="margin:0px; padding:0px; border:0px; background-color:transparent; vertical-align:middle;"
|-
| style="vertical-align:bottom; padding:0px; margin:0px; border:0px;" | Ägyptische Hieroglyphen können die Funktion von [[Schriftzeichen|Phonogrammen, Ideogrammen]] oder [[Determinativ]]en übernehmen. Die meisten Hieroglyphen können eine oder maximal zwei dieser Funktionen übernehmen, einzelne auch alle drei. Welche Funktion ein Zeichen hat, zeigt der Kontext, in vielen Fällen lassen sich die Verwendungen kaum abgrenzen. So ist das Zeichen <hiero>ra</hiero> Ideogramm in <hiero>ra:Z1</hiero> ''r<span class="Unicode">ˁ(w)</span>'' (Sonnengott) „Re“, in der vollständigeren Schreibung des gleichen Wortes als <hiero>r:a-ra:Z1</hiero> dient es nur als Determinativ; das Zeichen <hiero>pr</hiero> wird im Wort <hiero>pr:r-D54</hiero> ''pr(j)'' „herausgehen“ als Phonogramm ''pr'' aufgefasst, während es in <hiero>pr:Z1</hiero> ''pr(w)'' „Haus“ als Logogramm fungiert. Aufschluss darüber, ob und wie ein Zeichen gelesen werden kann, gibt im Allgemeinen die Zeichenliste der ''Egyptian Grammar'' von [[Alan Gardiner]],<ref>Gardiner 1927</ref> die jedoch nicht vollständig und in Einzelfällen überholt ist.
| style="vertical-align:bottom; padding:0px; margin:0px; border:0px;" |
| style="vertical-align:bottom; padding:0px; margin:0px; border:0px;" |
| style="vertical-align:bottom; padding:0px; margin:0px; border:0px;" |
| style="vertical-align:bottom; padding:0px; margin:0px; border:0px;" |
| style="vertical-align:bottom; padding:0px; margin:0px; border:0px;" |
| style="vertical-align:bottom; padding:0px; margin:0px; border:0px;" |
| style="vertical-align:bottom; padding:0px; margin:0px; border:0px;" |
| style="vertical-align:bottom; padding:0px; margin:0px; border:0px;" |
| style="vertical-align:bottom; padding:0px; margin:0px; border:0px;" |
| style="vertical-align:bottom; padding:0px; margin:0px; border:0px;" |
| style="vertical-align:bottom; padding:0px; margin:0px; border:0px;" |
| style="vertical-align:bottom; padding:0px; margin:0px; border:0px;" |
| style="vertical-align:bottom; padding:0px; margin:0px; border:0px;" |
| style="vertical-align:bottom; padding:0px; margin:0px; border:0px;" |
| style="vertical-align:bottom; padding:0px; margin:0px; border:0px;" |
| style="vertical-align:bottom; padding:0px; margin:0px; border:0px;" |
| style="vertical-align:bottom; padding:0px; margin:0px; border:0px;" |
| style="vertical-align:bottom; padding:0px; margin:0px; border:0px;" |
| style="vertical-align:bottom; padding:0px; margin:0px; border:0px;" |
|}
    """
    tree, reports = clean_markup(raw)

    assert (
            len(tree.get_child_nodes_by_class(Table)) == 0
    ), "single row/col Table not transformed to div"
    assert len(tree.get_child_nodes_by_class(Div)) == 1, "single row/col Table not transformed to div"


def test_remove_broken_children():
    raw = r"""
<ref>
 preformatted text
</ref>
    """

    tree, reports = clean_markup(raw)
    assert len(tree.get_child_nodes_by_class(PreFormatted)) == 0


def test_fix_nesting1():
    raw = """
:{|
|-
||bla||blub
|}
    """
    tree, reports = clean_markup(raw)
    table = tree.get_child_nodes_by_class(Table)[0]
    assert not table.get_parent_nodes_by_class(DefinitionDescription)


# changed with f94aa985f50d2db9749c57a7a5e22c0c8d487af4


@pytest.mark.xfail
def test_fix_nesting2():
    raw = r"""
<div><div>
* bla
* blub
</div></div>
    """
    tree, _ = clean_markup(raw)
    list_node = tree.get_child_nodes_by_class(ItemList)[0]
    assert not any(p.__class__ == Div for p in list_node.get_parents())


# the two tests below only make sense if paragraph nesting is forbidden - this is not the case anymore
# but maybe they are interesting in the future - therefore I did not delete them

# def test_fix_nesting3():
# raw = r'''
# <strike>
# para 1

# para 2
# </strike>
# '''

##     tree, reports = cleanMarkup(raw)
##     paras = tree.getChildNodesByClass(Paragraph)
# for para in paras:
##         assert not para.getChildNodesByClass(Paragraph)

# def test_fix_nesting4():
# raw = """
# <strike>

# <div>
# indented para 1

# regular para

# indented para 2

# </div>

# </strike>
# """

##     tree = getTreeFromMarkup(raw)
##     tree, reports = cleanMarkup(raw)
##     paras = tree.getChildNodesByClass(Paragraph)
# for para in paras:
##         assert not para.getChildNodesByClass(Paragraph)


def test_fix_nesting5():
    raw = """
<strike>
<div>

<div>

<div>
para 1
</div>

para 2
</div>

<div>
para 2
</div>

</div>
</strike>
    """

    tree, reports = clean_markup(raw)
    paras = tree.get_child_nodes_by_class(Paragraph)
    for para in paras:
        assert not para.get_child_nodes_by_class(Paragraph)


def test_fix_nesting6():
    raw = """''„Drei Affen, zehn Minuten.“'' <ref>Dilbert writes a poem and presents it to Dogbert:<poem style>
''DOGBERT: I once read that given infinite time, a thousand monkeys with typewriters would eventually write the complete works of Shakespeare.''
''DILBERT: But what about my poem?''
''DOGBERT: Three monkeys, ten minutes.“''</poem></ref>

<references/>
    """

    tree, reports = clean_markup(raw)
    show_tree(tree)
    from pprint import pprint

    pprint(reports)

    assert len(tree.get_child_nodes_by_class(Reference)) == 1


def test_swap_nodes():
    raw = r"""
<u><center>Text</center></u>
    """
    tree, _ = clean_markup(raw)
    center_node = tree.get_child_nodes_by_class(Center)[0]
    assert not any(p.__class__ == Underline for p in center_node.get_parents())


@pytest.mark.xfail
def test_split_big_table_cells():
    """
    Splitting big table cells can not properly be tested here.
    Testing needs to be done in the writers, since this test is writer
    specific and the output has to be verfied
    """
    assert False


@pytest.mark.xfail
def test_fix_paragraphs():
    raw = r"""  """  # FIXME: which markup results in paragraphs which are not properly nested with preceeding sections?
    clean_markup(raw)
    assert False


def test_clean_section_captions():
    raw = r"""
==<center>centered heading</center>==
bla
    """

    tree, _ = clean_markup(raw)
    section_node = tree.get_child_nodes_by_class(Section)[0]
    assert all(p.__class__ != Center for p in section_node.children[0].get_all_children())


def test_clean_section_captions2():
    raw = """=== ===
    bla
    """

    tree, _ = clean_markup(raw)
    assert len(tree.get_child_nodes_by_class(Section)) == 0


def num_br(tree):
    return len(tree.get_child_nodes_by_class(BreakingReturn))


def test_remove_breaking_returns_inside():
    # remove BRs at the inside 'borders' of block nodes
    raw = """
{|
|-
|<br/>blub<br/>
|text
|-
|<source></source><br/>text
| text
|-
|<br/><source></source><br/><br/>text
| text
|}
"""
    tree, reports = clean_markup(raw)  # 1 & 2
    assert num_br(tree) == 0


def test_remove_breaking_returns_outside():
    # remove BRs at the outside 'borders' of block nodes
    raw = """
<br/>

== section heading ==

<br/>

text

<br/>

<br/>

== section heading 2 ==

<br/><br/>

== section heading 3 ==
<br/>bla</br/>
"""

    tree, reports = clean_markup(raw)
    show_tree(tree)
    assert num_br(tree) == 0


def test_remove_breaking_returns_multiple():
    # remove BRs at the outside 'borders' of block nodes
    raw = """
paragraph

<br/>

<br/>

paragraph
"""

    tree, reports = clean_markup(raw)
    assert num_br(tree) == 0


# mwlib.refine creates a whitespace only paragraph containing the first
# br tag. in the old parser this first paragraph also contained the source node.


@pytest.mark.xfail
def test_remove_breaking_returns_no_remove():
    raw = """
<br/>
<source>
int main()
</source>

<br/>
 <br/> bla <br/> blub

ordinary paragraph. inside <br/> tags should not be removed
"""

    tree, reports = clean_markup(raw)
    # the only br tags that should remain after cleaning are the ones inside the preformatted node
    assert num_br(tree) == 3


def test_preserve_empty_text_nodes():
    raw = """[[blub]] ''bla''"""
    tree, reports = clean_markup(raw)
    p = [x for x in tree.find(Text) if x.caption == " "]
    assert len(p) == 1, "expected one space node"


def test_gallery():
    raw = """<gallery>
Image:There_Screenshot02.jpg|Activities include hoverboarding, with the ability to perform stunts such as dropping down from space
Image:Scenery.jpg|A wide pan over a seaside thatched-roof village
|Members can join and create interest groups
Image:Landmark02.jpg|There contains many landmarks, including a replica of New Orleans
Image:Emotes01.jpg|Avatars can display over 100 emotes
<!-- Deleted image removed: Image:Popoutemotes01.jpg|Avatars can display a wide variety of pop-out emotes -->
Image:Zona.jpg|Zona Island, a place where new members first log in.
Image:Hoverboat01.jpg|A member made vehicle. As an avatar users can paint and build a variety of items.
Image:|Zona Island, a place where new members first log in
<!-- Deleted image removed: Image:OldWaterinHole.jpg|The Old Waterin' Hole: a place where users can sit and chat while in a social club/bar-like environment. -->
</gallery>"""

    tree, reports = clean_markup(raw)
    gallery = tree.find(Gallery)[0]
    assert len(gallery.children) == 6


def test_remove_styles_without_text():
    raw = "'''bold text'''"
    tree, reports = clean_markup(raw)
    show_tree(tree)
    assert tree.find(Strong)

    raw = "text <em><br/></em> text"
    tree, reports = clean_markup(raw)
    show_tree(tree)
    assert tree.find(BreakingReturn) and not tree.find(Emphasized)


def test_split_table_lists1():
    raw = """
{|
|-
|
* item 1
* item 2
* item 3
* item 4
* item 5
* item 6

|
* item 7
* item 8
|}
    """
    tree, reports = clean_markup(raw)
    numrows = len(tree.get_child_nodes_by_class(Row))
    assert numrows == 6, "ItemList should have been splitted to 6 rows, numrows was: %d" % numrows


def test_split_table_lists2():
    raw = """
{|
|-
|
* item 1
** item 1.1
** item 1.2
** item 1.3
** item 1.4
** item 1.5
** item 1.6
* item 2
* item 3
* item 4
* item 5
* item 6

|
* item 7
* item 8
|}
    """
    tree, reports = clean_markup(raw)
    numrows = len(tree.get_child_nodes_by_class(Row))
    assert numrows == 6, "ItemList should have been splitted to 6 rows, numrows was: %d" % numrows


def test_remove_empty_section():
    raw = """
== section 1 ==

== section 2 ==

"""
    tree, reports = clean_markup(raw)
    assert len(tree.get_child_nodes_by_class(Section)) == 0, "section not removed"


def test_no_remove_empty_section():
    raw = """
== section 1 ==
[[Image:bla.png]]

== section 2 ==

[[Image:bla.png]]

== section 3 ==

<gallery>
Image:bla.png
</gallery>

== section 4 ==
<div>
[[Image:bla.png]]
</div>
"""

    tree, reports = clean_markup(raw)
    assert len(tree.get_child_nodes_by_class(Section)) == 4, "section falsly removed"
