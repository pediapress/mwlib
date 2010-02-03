#! /usr/bin/env python
#! -*- coding:utf-8 -*-

# Copyright (c) 2007, 2008, 2009 PediaPress GmbH
# See README.txt for additional licensing information.

import sys
import inspect

from mwlib import parser
from mwlib.advtree import (Article, ArticleLink, Big, Blockquote, Book, BreakingReturn, Caption, CategoryLink, Cell, Center, Chapter,
                           Cite, Code,DefinitionDescription, DefinitionList, DefinitionTerm, Deleted, Div, Emphasized, Gallery,
                           HorizontalRule, ImageLink, ImageMap, Inserted, InterwikiLink, Italic, Item, ItemList, LangLink, Link,
                           Math, NamedURL, NamespaceLink, Overline, Paragraph, PreFormatted, Reference, ReferenceList,
                           Row, Section, Small, Source, Span, SpecialLink, Strike, Strong, Sub, Sup, Table, Teletyped, Text, Timeline,
                           Underline, URL, Var)

from mwlib.writer import styleutils, miscutils

def show(node):
    parser.show(sys.stdout, node)


SKIPCHILDREN = 1
SKIPNOW = 2

# class CleanerError(RuntimeError):
#     pass

class TreeCleaner(object):

    start_clean_methods=['removeInvisibleLinks',
                         'removeNoPrint',
                         'removeInvalidFiletypes',
                         ]
    clean_methods=['removeEmptyTextNodes',
                   'handleListOnlyParagraphs', # FIXME: why not do this for all block nodes and not only for lists
                   'cleanSectionCaptions',
                   'removeChildlessNodes',
                   ]
    finish_clean_methods=['markShortParagraphs',
                          'markInfoboxes'
                          ]

    def __init__(self, tree, save_reports=False, nesting_strictness='loose', status_cb=None):

        # list of actions by the treecleaner
        # each cleaner method has to report its actions
        # this helps debugging and testing the treecleaner
        self.reports = []
        # reports are only saved, if set to True
        self.save_reports = save_reports
        self.status_cb=status_cb
        self.dirty_nodes = []

        # list of nodes which do not require child nodes
        self.childlessOK = [ArticleLink, BreakingReturn, CategoryLink, Cell, Chapter, Code, 
                            HorizontalRule, ImageLink, ImageMap, InterwikiLink, LangLink, Link, Math,
                            NamedURL, NamespaceLink, ReferenceList, Reference, SpecialLink, Text, Timeline, URL]
        # exceptions to the above. if any of the list items is explicitly set as a css style the node is not removed
        self.childless_exceptions = {Div: [u'width', u'height'],
                                     Span: [u'width', u'height'],}

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

        # remove ImageLinks which end with the following file types
        self.forbidden_file_endings = ['ogg']

    def getReports(self):
        return self.reports

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

        cleaner_methods = [getattr(self, method) for method in methods]

        while self.dirty_nodes:
            node = self.dirty_nodes.pop(0)
            for cleaner in cleaner_methods:
                result = cleaner(node)
                if result == SKIPNOW:
                    break

            if result == None:
                self.dirty_nodes.extend(node.children)

    def report(self, *args):
        if not self.save_reports:
            return
        caller = inspect.stack()[1][3]
        msg = ''
        if args:
            msg = ' '.join([repr(arg) for arg in args])        
        self.reports.append((caller, msg))        

    ################## UTILS

    def removeThis(self, node):
        parent = node.parent
        parent.removeChild(node)
        self.insertDirtyNode(parent)

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
            self.report('remove invisible link', node)
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
                self.report('removing child - keeping named reference', node)
                self._safeRemove(node, named_refs)
            else:
                self.report('removing child', node)
                self.removeThis(node)
            return SKIPCHILDREN


    def removeInvalidFiletypes(self, node):
        """remove ImageLinks which end with the following file types"""
        if node.__class__ == ImageLink:
            ext = node.target.rsplit('.', 1)[-1] if '.' in node.target else None
            if ext in self.forbidden_file_endings:
                self.report("removed invalid 'image' type with target %r", node.target)
                self.removeThis(node)


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
            self.removeThis(node)
            self.report('removed empty text node')
            return SKIPCHILDREN

    def handleListOnlyParagraphs(self, node):
        if node.__class__ == Paragraph \
               and node.children \
               and all([c.__class__ == ItemList for c in node.children]):
            parent = node.parent
            parent.replaceChild(node, node.children)
            self.report('replaced children:', node, '-->', node.children, 'for node:', node.parent)
            self.insertDirtyNode(parent)
            return SKIPNOW

    def cleanSectionCaptions(self, node):
        """Remove all block nodes from Section nodes, keep the content. If section title is empty replace section by br node"""

        if node.__class__ == Section:
            if not node.children:
                self.report('section contained no children')
                return
            caption_node = node.children[0]
            if not caption_node.getAllDisplayText():
                children = [BreakingReturn()]
                if len(node.children) > 1: # at least one "content" node
                    children.extend(node.children)
                self.report('replaced section with empty title with br node')
                node.parent.replaceChild(node, children)
            
            children = caption_node.getAllChildren() # remove all block nodes
            for c in children:
                if c.isblocknode:
                    self.report('removed block node', c)
                    c.parent.replaceChild(c, c.children)


    def removeChildlessNodes(self, node):
        """Remove nodes that have no children except for nodes in childlessOk list."""   
        is_exception = False
        if node.__class__ in self.childless_exceptions.keys() and node.style:
            for style_type in self.childless_exceptions[node.__class__]:
                if style_type in node.style.keys():
                    is_exception = True

        if not node.children and node.__class__ not in self.childlessOK and not is_exception:
            if node.parent.__class__ == Section and not node.previous: 
                return # make sure that the first child of a section is not removed - this is the section caption
            removeNode = node
            while removeNode.parent and not removeNode.siblings and removeNode.parent.__class__ not in self.childlessOK:
                removeNode = removeNode.parent
            if removeNode.parent:
                self.report('removed:', removeNode)
                removeNode.parent.removeChild(removeNode)
        for c in node.children[:]:
            self.removeChildlessNodes(c)


    #################### END CLEAN

    def markShortParagraphs(self, node):
        """Hint for writers that allows for special handling of short paragraphs """
        if node.__class__ == Paragraph \
               and len(node.getAllDisplayText()) < 80 \
               and not node.getParentNodesByClass(Table) \
               and not any([c.isblocknode for c in node.children]):
            node.short_paragraph = True

    def markInfoboxes(self, node):
        if node.__class__ == Article:
            tables = node.getChildNodesByClass(Table)
            found_infobox = False
            for table in tables:
                if miscutils.hasInfoboxAttrs(table):
                    table.isInfobox = found_infobox = True
            if found_infobox or not tables:
                return
            if miscutils.articleStartsWithTable(node, max_text_until_infobox=200):
                tables[0].isInfobox = True


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
