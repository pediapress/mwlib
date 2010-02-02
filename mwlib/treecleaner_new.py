#! /usr/bin/env python
#! -*- coding:utf-8 -*-

# Copyright (c) 2007, 2008, 2009 PediaPress GmbH
# See README.txt for additional licensing information.

import sys

from mwlib import parser
from mwlib.advtree import (Article, ArticleLink, Big, Blockquote, Book, BreakingReturn, Caption, CategoryLink, Cell, Center, Chapter,
                           Cite, Code,DefinitionDescription, DefinitionList, DefinitionTerm, Deleted, Div, Emphasized, Gallery,
                           HorizontalRule, ImageLink, ImageMap, Inserted, InterwikiLink, Italic, Item, ItemList, LangLink, Link,
                           Math, NamedURL, NamespaceLink, Overline, Paragraph, PreFormatted, Reference, ReferenceList,
                           Row, Section, Small, Source, Span, SpecialLink, Strike, Strong, Sub, Sup, Table, Teletyped, Text, Timeline,
                           Underline, URL, Var)


def show(node):
    parser.show(sys.stdout, node)

SKIPCHILDREN = 1


class CleanerError(RuntimeError):
    pass

class TreeCleaner(object):

    start_clean_methods=['invisibleLinks',
                         'noPrint',
                         ]
    clean_methods=['emptyTextNodes',
                   ]
    finish_clean_methods=[]

    def __init__(self, tree, save_reports=False, nesting_strictness='loose', status_cb=None):
        self.dirty_nodes = []
        
    def getReports(self):
        return []

    def clean(self, tree):
        print '*'*20, 'START cleaning'
        self.dirty_nodes = [tree]
        while self.dirty_nodes:
            self.clean_tree(methods=self.start_clean_methods)

        print '*'*20, 'MAIN cleaning'
        self.dirty_nodes = [tree]
        while self.dirty_nodes:
            self.clean_tree(methods=self.clean_methods)

        print '*'*20, 'STOP cleaning'
        self.dirty_nodes = [tree]
        while self.dirty_nodes:
            self.clean_tree(methods=self.finish_clean_methods)


        
    def clean_tree(self, methods=[]):

        node = self.dirty_nodes.pop(0)       
        if not node:
            return

        result = None

        for method_name in methods:
            try:
                method_condition = getattr(self, method_name + 'Cond')
                method_action = getattr(self, method_name + 'Action')
            except AttributeError:
                raise CleanerError('Cleaner method or action not implemented for name: %r' % method_name)
            if method_condition(node):
                print 'CLEANING:', method_name, node.__class__.__name__
                result = method_action(node)
                       
        if not result == SKIPCHILDREN:
            self.dirty_nodes.extend(node.children)

    #################### START CLEAN

    def invisibleLinksCond(self, node):
        return node.__class__ in [CategoryLink, LangLink] and not node.colon

        
    def invisibleLinksAction(self, node):
        node.parent.removeChild(node)
        return SKIPCHILDREN

    # list of css classes OR id's which trigger the removal of the node from the tree
    noDisplayClasses = ['hiddenStructure',
                        'dablink',
                        'editlink',
                        'metadata',
                        'noprint',
                        'portal',
                        'sisterproject',
                        'NavFrame',
                        'geo-multi-punct',
                        'coordinates_3_ObenRechts',
                        'microformat',
                        'navbox',
                        'navbox-vertical',
                        'Vorlage_Gesundheitshinweis',
                        ]

    def _getNamedRefs(self, node):
        named_refs= []
        for n in node.getChildNodesByClass(Reference) + [node]:
            if n.__class__ == Reference and n.attributes.get('name'):
                named_refs.append(n)
        return named_refs

    def _safeRemove(self, node, named_refs):
        if node in named_refs:
            node.no_display = True
            return
        for ref in named_refs:
            ref.no_display = True
            table_parents = node.getParentNodesByClass(Table)
            if table_parents:
                ref.moveto(table_parents[0], prefix=True)
            else:
                ref.moveto(node, prefix=True)
        node.parent.removeChild(node)


    def noPrintCond(self, node):
        return (node.hasClassID(self.noDisplayClasses) or not node.visible) and node.parent

    def noPrintAction(self, node):
        named_refs = self._getNamedRefs(node)
        if named_refs:
            self._safeRemove(node, named_refs)
        else:
            node.parent.removeChild(node)
        return SKIPCHILDREN


    ####################### MAIN CLEAN
    
    def emptyTextNodesCond(self, node):        
        """Removes Text nodes which contain no text at all.

        Text nodes which only contain whitespace are kept.
        """
        return node.__class__ == Text \
               and (not node.caption \
                    or (node.previous \
                        and node.previous.isblocknode \
                        and node.next \
                        and node.next.isblocknode \
                        and not node.caption.strip()))
        
    def emptyTextNodesAction(self, node):
        node.parent.removeChild(node)
        return SKIPCHILDREN

