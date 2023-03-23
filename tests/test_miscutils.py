#! /usr/bin/env py.test
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.
import sys

from mwlib import parser
from mwlib.dummydb import DummyDB
from mwlib.uparser import parseString
from mwlib.writer import miscutils


def get_tree_from_markup(raw):
    return parseString(title="Test", raw=raw, wikidb=DummyDB())


def show(tree):
    parser.show(sys.stdout, tree)


def test_article_starts_with_infobox_1():
    raw = """
Some text in a paragraph

Some text in a paragraph [[http://ysfine.com]]

{| class="infobox"
|-
| bla || bla
|}

Some more text
"""
    tree = get_tree_from_markup(raw)
    # show(tree)
    assert miscutils.articleStartsWithInfobox(tree, max_text_until_infobox=100) is True
    assert miscutils.articleStartsWithInfobox(tree, max_text_until_infobox=10) is False
