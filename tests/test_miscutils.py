#! /usr/bin/env py.test
# -*- coding: utf-8 -*-
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

import sys
from mwlib.dummydb import DummyDB
from mwlib.uparser import parseString
from mwlib import parser
from mwlib.writer import miscutils


def getTreeFromMarkup(raw):
    return parseString(title="Test", raw=raw, wikidb=DummyDB())


def show(tree):
    parser.show(sys.stdout, tree)

def test_articleStartsWithInfobox1():

    raw = '''
Some text in a paragraph

Some text in a paragraph [[http://ysfine.com]]

{| class="infobox"
|-
| bla || bla
|}

Some more text
'''
    tree = getTreeFromMarkup(raw)
    #show(tree)
    assert miscutils.articleStartsWithInfobox(tree, max_text_until_infobox=100) == True
    assert miscutils.articleStartsWithInfobox(tree, max_text_until_infobox=10) == False

