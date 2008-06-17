#! /usr/bin/env python
#! -*- coding:utf-8 -*-

# Copyright (c) 2007, PediaPress GmbH
# See README.txt for additional licensing information.

from mwlib import advtree
from mwlib.advtree import Paragraph, PreFormatted, ItemList, Div, Reference, Cite, Item, Article, Section
from mwlib.advtree import Text, Cell, Link, Math, URL, BreakingReturn, HorizontalRule, CategoryLink
from mwlib.advtree import SpecialLink, ImageLink, ReferenceList, Chapter, NamedURL, LangLink, Table
               
def fixLists(node): 
    """
    all ItemList Nodes that are the only children of a paragraph are moved out of the paragraph.
    the - now empty - paragraph node is removed afterwards
    """
    if node.__class__ == advtree.ItemList and node.parent and node.parent.__class__ == Paragraph:
        if not node.siblings and node.parent.parent:
            node.parent.parent.replaceChild(node.parent,[node])        
    for c in node.children[:]:
        fixLists(c)


childlessOK = [Text, Cell, Link, Math, URL, BreakingReturn, HorizontalRule, CategoryLink, LangLink,
               SpecialLink, ImageLink, ReferenceList, Chapter, NamedURL]

def removeChildlessNodes(node):
    """
    remove nodes that have no children except for nodes in childlessOk list
    """   

    if not node.children and node.__class__ not in childlessOK:
        removeNode = node
        while removeNode.parent and not removeNode.siblings:
            removeNode = removeNode.parent
        if removeNode.parent:
            removeNode.parent.removeChild(removeNode)

    for c in node.children[:]:
        removeChildlessNodes(c)

def removeLangLinks(node):
    """
    removes the language links that are listed below an article. language links
    inside the article should not be touched
    """

    txt = []
    langlinkCount = 0

    for c in node.children:
        if c.__class__ == LangLink:
            langlinkCount +=1
        else:
            txt.append(c.getAllDisplayText())
    txt = ''.join(txt).strip()
    if langlinkCount and not txt and node.parent:
        node.parent.removeChild(node)

    for c in node.children[:]:
        removeLangLinks(c)





def _fixParagraphs(element):
    if isinstance(element, advtree.Paragraph) and isinstance(element.previous, advtree.Section) \
            and element.previous is not element.parent:
        prev = element.previous
        parent = element.parent
        element.moveto(prev.getLastChild())
        return True # changed
    else:
        for c in element.children[:]:
            if _fixParagraphs(c):
                return True


def fixParagraphs(root):
    while _fixParagraphs(root):
        print "_run fix paragraphs"

    


def _fixBlockElements(element):
    """
    the parser uses paragraphs to group anything
    this is not compatible with xhtml where nesting of 
    block elements is not allowed.
    """
    blockelements = (advtree.Paragraph, advtree.PreFormatted, advtree.ItemList,advtree.Section, advtree.Table,
                     advtree.Blockquote, advtree.DefinitionList, advtree.HorizontalRule)

    if isinstance(element, blockelements) and element.parent and isinstance(element.parent, blockelements) \
            and not isinstance(element.parent, advtree.Section) : # Section is no problem if parent
        if not element.parent.parent:
            print "missing parent parent", element, element.parent, element.parent.parent
            assert element.parent.parent
        
        # s[ p, p[il[], text], p] -> s[p, p, il, p[text], p]
        # split element parents
        pstart = element.parent.copy()
        pend = element.parent.copy()
        for i,c in enumerate(element.parent.children):
            if c is element:
                break
        pstart.children = pstart.children[:i]
        pend.children = pend.children[i+1:]
        print "action",  [pstart, element, pend]
        grandp = element.parent.parent
        oldparent = element.parent
        grandp.replaceChild(oldparent, [pstart, element, pend])
        return True # changed
    else:
        for c in element.children:
            if _fixBlockElements(c):
                return True
        
def fixBlockElements(root):
    while _fixBlockElements(root):
        print "_run fix block elements"
        
                
