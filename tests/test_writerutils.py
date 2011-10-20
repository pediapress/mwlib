#! /usr/bin/env py.test
# -*- coding: utf-8 -*-
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

import sys

from mwlib import parser
from mwlib import advtree
from mwlib.treecleaner import TreeCleaner
from mwlib.writer import styleutils

def showTree(tree):
    parser.show(sys.stdout, tree, 0)

def getTreeFromMarkup(raw):
    from mwlib.dummydb import DummyDB
    from mwlib.uparser import parseString
    return parseString(title="Test", raw=raw, wikidb=DummyDB())

def buildAdvTree(raw):
    tree  = getTreeFromMarkup(raw)
    advtree.buildAdvancedTree(tree)
    tc = TreeCleaner(tree, save_reports=True)
    tc.cleanAll(skipMethods=[])
    return tree

def test_textalign1():
    raw = '''
{|
|-
| style="text-align:right;" | right aligned
| style="text-align:left;" | left aligned
|-
| style="text-align:center;" | centered
| style="text-align:bogus;" | bogus align --> left
|}
'''
    tree = buildAdvTree(raw)
    cells = tree.getChildNodesByClass(advtree.Cell)
    correct_align = ['right', 'left', 'center', 'left']
    for (i, cell) in enumerate(cells):
        align = styleutils.getTextAlign(cell)
        assert align == correct_align[i], 'styleutils.getCelTextAlign return false alignment'


def test_textalign2():
    raw = '''
{| style="text-align:right;" class="prettytable"
|- style="text-align:center;"
| style="text-align:left;" | left aligned
| centered
|-
| right aligned
| style="text-align:center;" | centered
|-
| align="center" | centered
| align="left" | left
|}


<center>
some centered text

<div style="text-align:left;">
left aligned div in the middle
</div>

and more centering
</center>
'''
    tree = buildAdvTree(raw)
    tree.show()
    cells = tree.getChildNodesByClass(advtree.Cell)
    correct_align = ['left', 'center', 'right', 'center', 'center', 'left']
    for (i, cell) in enumerate(cells):
        align = styleutils.getTextAlign(cell)
        assert align == correct_align[i], 'styleutils.getCelTextAlign return false alignment'

    center = tree.getChildNodesByClass(advtree.Center)
    texts = center[0].getChildNodesByClass(advtree.Text)
    correct_align = ['center', 'left', 'center']
    for (i, txt) in enumerate(texts):
        assert styleutils.getTextAlign(txt) == correct_align[i], 'styleutils.getCelTextAlign return false alignment'


def test_textalign3():
    raw = '''
{| style="text-align:right;width:100%;" class="prettytable"
|-
| right aligned text that gives us some space
| more text, text, text
|- align="center"
| style="text-align:left;" | left aligned
| centered
|}
'''
    tree = buildAdvTree(raw)
    cells = tree.getChildNodesByClass(advtree.Cell)
    correct_align = ['right', 'right', 'left', 'center']
    for (i, cell) in enumerate(cells):
        align = styleutils.getTextAlign(cell)
        assert align == correct_align[i], 'styleutils.getCelTextAlign return false alignment'
