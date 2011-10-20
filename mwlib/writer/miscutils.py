#! /usr/bin/env python
#! -*- coding:utf-8 -*-

# Copyright (c) 2007, 2008, 2009 PediaPress GmbH
# See README.rst for additional licensing information.

from __future__ import division

from mwlib import advtree

def hasInfoboxAttrs(node):
    infobox_classIDs = ['infobox', 'taxobox']
    if node.hasClassID(infobox_classIDs):
        return True
    if node.attributes.get('summary', '').lower() in infobox_classIDs:
        return True    
    return False

def textInNode(node):
    amap = {advtree.Text:"caption", advtree.Link:"target", advtree.URL:"caption", advtree.Math:"caption", advtree.ImageLink:"caption" }
    access = amap.get(node.__class__, "")
    if access:
        txt = getattr(node, access)
        if txt:
            return len(txt)
        else:
            return 0
    else:
        return 0

def textBeforeInfoBox(node, infobox, txt_list=[]):
    txt_list.append((textInNode(node), node==infobox))        
    for c in node:
        textBeforeInfoBox(c, infobox, txt_list)
    sum_txt = 0    
    for len_txt, is_infobox in txt_list:
        sum_txt += len_txt
        if is_infobox:
            return sum_txt
    return sum_txt

def articleStartsWithInfobox(article_node, max_text_until_infobox=0):
    assert article_node.__class__ == advtree.Article, 'articleStartsWithInfobox needs to be called with Article node'
    infobox = None
    for table in article_node.getChildNodesByClass(advtree.Table):
        if hasInfoboxAttrs(table):
            infobox = table
    if not infobox:
        return False
    return textBeforeInfoBox(article_node, infobox, []) <= max_text_until_infobox


def articleStartsWithTable(article_node, max_text_until_infobox=0):
    assert article_node.__class__ == advtree.Article, 'articleStartsWithInfobox needs to be called with Article node'
    tables = article_node.getChildNodesByClass(advtree.Table)
    if not tables:
        return False
    return textBeforeInfoBox(article_node, tables[0], []) <= max_text_until_infobox

    
