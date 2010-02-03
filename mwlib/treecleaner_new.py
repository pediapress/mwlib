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
SKIPNOW = 2

# class CleanerError(RuntimeError):
#     pass

class TreeCleaner(object):

    start_clean_methods=['removeInvisibleLinks',
                         'removeNoPrint',
                         ]
    clean_methods=['removeEmptyTextNodes',
                   'handleListOnlyParagraphs', # FIXME: why not do this for all block nodes and not only for lists
                   #'fireAtWill',
                   ]
    finish_clean_methods=['markShortParagraph',
                          ]

    def __init__(self, tree, save_reports=False, nesting_strictness='loose', status_cb=None):
        self.dirty_nodes = []
        
        # list of css classes OR id's which trigger the removal of the node from the tree
        self.noDisplayClasses = ['hiddenStructure',
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


    def getReports(self):
        return []

    def clean(self, tree):
        self.setNodeIds(tree) # FIXME: used for debugging - disable in production
        print '*'*20, 'START cleaning'
        self.clean_tree(tree, methods=self.start_clean_methods)

        print '*'*20, 'MAIN cleaning'
        self.clean_tree(tree, methods=self.clean_methods)

        print '*'*20, 'STOP cleaning'
        self.clean_tree(tree, methods=self.finish_clean_methods)

    def clean_tree(self, tree, methods=[]):
        self.dirty_nodes = [tree]
        while self.dirty_nodes:
            node = self.dirty_nodes.pop(0)

            for method in methods:
                cleaner = getattr(self, method)
                result = cleaner(node)
                if result != None:
                    print 'cleaned:', cleaner.__name__, 'result:', result                    
                if result == SKIPNOW:
                    break

            if result == None:
                self.dirty_nodes.extend(node.children)

    def insertDirtyNode(self, insert_node):
        '''Add a node to the dirty queue and delete all sub-nodes'''
        sub_nodes = []
        for node in self.dirty_nodes:
            if insert_node in node.getParents():
                sub_nodes.append(node)
        for node in sub_nodes:
            self.dirty_nodes.remove(node)
        self.dirty_nodes.insert(0, insert_node)


    #################### START CLEAN

    def removeInvisibleLinks(self, node):
        if node.__class__ in [CategoryLink, LangLink] and not node.colon:
            node.parent.removeChild(node)
            return SKIPCHILDREN

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


    def removeNoPrint(self, node):
        if (node.hasClassID(self.noDisplayClasses) or not node.visible):
            named_refs = self._getNamedRefs(node)
            if named_refs:
                self._safeRemove(node, named_refs)
            else:
                node.parent.removeChild(node)
            return SKIPCHILDREN


    ####################### MAIN CLEAN
    
        
    def removeEmptyTextNodes(self, node):
        """Removes Text nodes which contain no text at all.

        Text nodes which only contain whitespace are kept.
        """
        if node.__class__ == Text \
               and (not node.caption \
                    or (not node.caption.strip() \
                        and node.previous \
                        and node.previous.isblocknode \
                        and node.next \
                        and node.next.isblocknode)):            
            node.parent.removeChild(node)
            return SKIPCHILDREN

    def handleListOnlyParagraphs(self, node):
        if node.__class__ == Paragraph \
               and node.children \
               and all([c.__class__ == ItemList for c in node.children]):
            print 'FOUND BAD LIST'
            target = node.parent
            target.replaceChild(node, node.children)
            #self.dirty_nodes.insert(0, target)
            self.insertDirtyNode(target)
            return SKIPNOW

    #################### END CLEAN

    def markShortParagraph(self, node):
        """Hint for writers that allows for special handling of short paragraphs """
        if node.__class__ == Paragraph \
               and len(node.getAllDisplayText()) < 80 \
               and not node.getParentNodesByClass(Table) \
               and not any([c.isblocknode for c in node.children]):
            node.short_paragraph = True

    ################# DEBUG STUFF

    def fireAtWill(self, node):
        if node.__class__ == ItemList:
            node.vlist['fireAtWill'] = 'HIT'

    node_id = 0
    def setNodeIds(self, node):
        node.vlist['CLEANER_ID']= self.node_id
        self.node_id += 1
        for c in node.children:
            self.setNodeIds(c)
