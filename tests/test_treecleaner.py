#! /usr/bin/env py.test
# -*- coding: utf-8 -*-
# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.

import sys

from mwlib.advtree import buildAdvancedTree
from mwlib import parser
from mwlib.treecleaner import TreeCleaner
from mwlib.advtree import (Article, ArticleLink, Blockquote, BreakingReturn, CategoryLink, Cell, Center, Chapter,
                     Cite, Code, DefinitionList, Div, Emphasized, HorizontalRule, ImageLink, InterwikiLink, Item,
                     ItemList, LangLink, Link, Math, NamedURL, NamespaceLink, Paragraph, PreFormatted,
                     Reference, ReferenceList, Row, Section, Source, SpecialLink, Table, Text, Underline,
                     URL)


def _treesanity(r):
    "check that parents match their children"
    for c in r.allchildren():
        if c.parent:
            assert c in c.parent.children
            assert len([x for x in c.parent.children if x is c]) == 1
        for cc in c:
            assert cc.parent
            assert cc.parent is c
            

def getTreeFromMarkup(raw):
    from mwlib.dummydb import DummyDB
    from mwlib.uparser import parseString
    return parseString(title="Test", raw=raw, wikidb=DummyDB())
    
def cleanMarkup(raw):
    tree  = getTreeFromMarkup(raw)
    buildAdvancedTree(tree)
    tc = TreeCleaner(tree, save_reports=True)
    tc.cleanAll()
    reports = tc.getReports()
    return (tree, reports)

def cleanMarkupSingle(raw, cleanerMethod):
    tree  = getTreeFromMarkup(raw)
    buildAdvancedTree(tree)
    tc = TreeCleaner(tree, save_reports=True)
    tc.clean([cleanerMethod])
    reports = tc.getReports()
    return (tree, reports)
    

def showTree(tree):
    parser.show(sys.stderr, tree, 0)
    

def _all(list):
    for item in list:
        if item == False:
            return False
    return True

def test_fixLists():
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
    tree, reports = cleanMarkup(raw)
    lists = tree.getChildNodesByClass(ItemList)
    for li in lists:
        assert _all([p.__class__ != Paragraph for p in li.getParents()])
    _treesanity(tree)   

def test_fixLists2():
    raw = r"""
* list item 1
* list item 2
some text in the same paragraph
    """
    
    tree, reports = cleanMarkup(raw)
    #tree, reports = cleanMarkupSingle(raw, 'fixLists')
    showTree(tree)
    print reports
    assert False
    
def test_removebrakingreturn():
    raw = r"""
{| class="prettytable"  width="100%"
|width="30%"|'''Preis'''
|width="34%"|'''Preisträger / Film / Serie'''
|width="36%"|'''Nominierungen'''
|-
| '''Bester Fernsehfilm/Mehrteiler'''
|"Rose" (ARD/BR/SWR/ARTE)
|<small> [[2030 – Aufstand der Alten]] (ZDF)</small> </br>
<small> Der Butler und die Prinzessin (Sat.1)</small> </br>
<small> [[Die Flucht (2007)|Die Flucht]] (ARD/ARTE)</small> </br>
<small> [[Vom Ende der Eiszeit]] (ARD/ARTE)</small>
|-
| '''Bester Schnitt'''
|[[Florian Drechsler]] für Sperling und die kalte Angst (ZDF)
|<small> </small> </br>
<small> [[Clara Fabry]] für Helen, Fred und Ted (ARD)</small> </br>
<small> [[Dagmar Lichius]] für [[Post Mortem]] (RTL)</small>
|}
""".decode("utf8")

    tree, reports = cleanMarkup(raw)
    assert len(tree.getChildNodesByClass(BreakingReturn)) == 4
    _treesanity(tree)


def test_removebrakingreturn2():
    raw = """
blub

<br style="clear:both" />

<br />

===Mannschaft===
""".decode("utf8")

    tree, reports = cleanMarkup(raw)
    assert len(tree.getChildNodesByClass(BreakingReturn)) == 0
    _treesanity(tree)


def test_removebrakingreturn3():
    raw = """
blub
<br />""".decode("utf8")

    tree, reports = cleanMarkup(raw)    
    assert len(tree.getChildNodesByClass(BreakingReturn)) == 0
    _treesanity(tree)


def test_removebrakingreturn4():
    raw = """
[[Yokosuka Kaigun Kosho]]<br />(Marinewerft [[Yokosuka]])
""".decode("utf8")

    tree, repotrs = cleanMarkup(raw)
    showTree(tree)
    assert len(tree.getChildNodesByClass(BreakingReturn)) == 1
    _treesanity(tree)

