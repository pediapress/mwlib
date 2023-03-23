#! /usr/bin/env py.test
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

import sys

from mwlib import advtree, parser
from mwlib.dummydb import DummyDB
from mwlib.uparser import parseString
from mwlib.writer import styleutils


def get_tree_from_markup(raw):
    tree = parseString(title="Test", raw=raw, wikidb=DummyDB())
    advtree.buildAdvancedTree(tree)
    return tree


def show(tree):
    parser.show(sys.stdout, tree)


def test_get_text_align():
    raw = """
{|
|-
! center
! style="text-align:right;"|right
|- style="text-align:left;"
! left
! style="text-align:right;"|right
|}
    """
    tree = get_tree_from_markup(raw)
    for cell in tree.getChildNodesByClass(advtree.Cell):
        txt = cell.getAllDisplayText().strip()
        align = styleutils.getTextAlign(cell)
        assert txt == align, "alignment not correctly parsed"


def test_get_text_align2():
    raw = """
left

<div style="text-align:right;">
right

<div style="text-align:left;">
left

{| class="prettytable"
|-
| left
| style="text-align:right;" | right
|}

{| class="prettytable" style="text-align:right;"
|-
| right
| style="text-align:center;" | center
|}
</div>
</div>"""

    tree = get_tree_from_markup(raw)
    for cell in tree.getChildNodesByClass(advtree.Cell):
        txt = cell.getAllDisplayText().strip()
        align = styleutils.getTextAlign(cell)

        if txt != align:
            show(cell)

        assert txt == align, "alignment not correctly parsed. expected:|{}|, got |{}|".format(
            txt,
            align,
        )
