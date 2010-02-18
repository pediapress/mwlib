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
                         'removeBlacklistedNodes', 
                         'buildDefinitionLists',
                         ]
    clean_methods=['removeEmptyTextNodes',
                   'removeTextlessStyles',
                   'removeBreakingReturns',
                   'handleListOnlyParagraphs', # FIXME: why not do this for all block nodes and not only for lists
                   #'simplifyBlockNodes', # FIXME: paragraphs with one block node child are removed MERGE WITH THE ABOVE
                   'cleanSectionCaptions',
                   'removeChildlessNodes',
                   #'fixParagraphs' FIXME: probably not needed. otherwise a proper node-nesting check should be performed
                   'removeBrokenChildren',
                   'fixNesting',
                   'removeDuplicateLinksInReferences',
                   'filterChildren',
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

        self.style_nodes = [Italic, Emphasized, Strong, Overline, Underline, Sub, Sup, Small, Big, Var]

        self.inlineStyleNodes = [Big, Center, Cite, Code, Deleted, Emphasized, Inserted, Italic,
                                 Overline, Small, Strike, Strong, Sub, Sup, Teletyped, Underline, Var]

        # USED IN fixNesting if nesting_strictness == 'loose'
        # keys are nodes, that are not allowed to be inside one of the nodes in the value-list
        # ex: pull image links out of preformatted nodes
        # fixme rename to ancestors
        self.forbidden_parents = {ImageLink:[PreFormatted],
                                  ItemList:[Div, PreFormatted],
                                  Source:self.inlineStyleNodes,
                                  DefinitionList:[Paragraph],
                                  Blockquote:[PreFormatted],
                                  Center:[PreFormatted],
                                  Paragraph:[PreFormatted],
                                  Section:[PreFormatted],
                                  Gallery:[PreFormatted, DefinitionDescription, DefinitionList, DefinitionTerm],
                                  Table:[DefinitionList]
                                  }
        self.forbidden_parents[Source].append(PreFormatted)

        # when checking nesting, some Nodes prevent outside nodes to be visible to inner nodes
        # ex: Paragraphs can not be inside Paragraphs. but if the inner paragraph is inside a
        # table which itself is inside a paragraph this is not a problem
        self.outsideParentsInvisible = [Table, Section, Reference]
        self.nesting_strictness = nesting_strictness # loose | strict

        # ex: delete preformatted nodes which are inside reference nodes,
        # all children off the preformatted node are kept
        self.removeNodes = {PreFormatted: [Reference, PreFormatted],
                            Cite: [Item, Reference],
                            Code: [PreFormatted],
                            ImageLink: [Reference],
                            Div: [Reference, Item],
                            Center:[Reference],
                            Teletyped:[Reference],
                            ReferenceList: [Reference],
                            Teletyped: [Source],
                            }

        self.node_blacklist = []

        # keys are nodes which can only have child nodes of types inside the valuelist.
        # children of different classes are deleted
        self.nodeFilter = {ItemList:[Item],
                           Gallery: [ImageLink],
                           }


        
    def getReports(self):
        return self.reports

    def clean(self, tree):
        self.tree = tree
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
            assert node, 'None in dirty node queue'
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
        print caller, msg # FIXME: remove for production use


    ################## UTILS

    def firstCheck(self, node):
        cleaner_method = inspect.stack()[1][3]
        check_flag = 'tc_%s' % cleaner_method
        if hasattr(node, check_flag):
            return False
        else:
            setattr(node, check_flag, True)
            return True

    def removeThis(self, node):
        parent = node.parent
        self.insertDirtyNode(parent)
        parent.removeChild(node)
        assert all([dn is not node for dn in self.dirty_nodes]), 'node should have been removed from dirty queue'

    def insertDirtyNode(self, insert_node):
        '''Add a node to the dirty queue and delete all sub-nodes'''
        assert insert_node, 'insert_node can not be None'
        if insert_node in self.dirty_nodes and False: # move node to start of queue
            self.dirty_nodes.remove(insert_node)
            self.dirty_nodes.insert(0, insert_node)
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
            self.removeThis(node)
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


    def removeBlacklistedNodes(self, node):
        if node.__class__ in self.node_blacklist:
            self.report('removed blacklisted node', node)
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
            self.report('removed empty text node', node.vlist.get('CID'))
            return SKIPNOW

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
                self.removeThis(removeNode)
                return SKIPNOW


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


    def removeTextlessStyles(self, node):
        """Remove style nodes that have no children with text"""
        if node.__class__ in self.style_nodes:
            if not node.getAllDisplayText().strip() and node.parent:
                if node.children:
                    parent = node.parent
                    parent.replaceChild(node, newchildren=node.children)
                    self.insertDirtyNode(parent)
                    self.report('remove style', node, 'with text-less children', node.children )
                    return SKIPNOW
                else:
                    self.removeThis(node)                    
                    self.report('removed style without children', node)
                    return SKIPNOW

    def _nestingBroken(self, node):
        # FIXME: the list below is used and not node.isblocknode. is there a reason for that?
        blocknodes = (Paragraph, PreFormatted, ItemList, Section, Table,
                      Blockquote, DefinitionList, HorizontalRule, Source)
        parents = node.getParents()

        clean_parents = []
        parents.reverse()
        for p in parents:
            if p.__class__ not in self.outsideParentsInvisible:
                clean_parents.append(p)
            else:
                break
        #clean_parents.reverse()
        parents = clean_parents

        if self.nesting_strictness == 'loose':
            for parent in parents:
                if parent.__class__ in self.forbidden_parents.get(node.__class__, []):
                    return parent
        elif self.nesting_strictness == 'strict':
            for parent in parents:
                if node.__class__ != Section and node.__class__ in blocknodes and parent.__class__ in blocknodes:
                    return parent
        return None
           

    def _markNodes(self, node, divide, problem_node=None):
        got_divide = False
        for c in node.children:
            if getattr(node, 'nesting_pos', None):
                c.nesting_pos = node.nesting_pos
                continue
            if c in divide:
                got_divide = True
                if c == problem_node:
                    c.nesting_pos = 'problem'
                continue
            if not got_divide:
                c.nesting_pos = 'top'
            else:
                c.nesting_pos = 'bottom'
        for c in node.children:
            self._markNodes(c, divide, problem_node=problem_node)

    def _cleanUpMarks(self, node):
        if hasattr(node, 'nesting_pos'):
            del node.nesting_pos
        for c in node.children:
            self._cleanUpMarks(c)
            
    def _filterTree(self, node, nesting_filter=[]):
        if getattr(node, 'nesting_pos', None) in nesting_filter:
            node.parent.removeChild(node)
            return
        for c in node.children[:]:
            self._filterTree(c, nesting_filter=nesting_filter)

    def fixNesting(self, node):
        """Nesting of nodes is corrected.

        The strictness depends on nesting_strictness which can either be 'loose' or 'strict'.
        Depending on the strictness the _nestingBroken method uses different approaches to
        detect forbidden nesting.

        Example for 'strict' setting: (bn --> blocknode, nbn --> nonblocknode)
        bn_1
         nbn_2
         bn_3
         nbn_4

        becomes:
        bn_1.1
         nbn_2
        bn_3
        bn_1.2
         nbn_4
        """

        bad_parent = self._nestingBroken(node)
        if not bad_parent:
            return

        # since we copy the tree, we need to clean and update the dirty queue first
        self.insertDirtyNode(bad_parent.parent)

        divide = node.getParents()
        divide.append(node)
        self._markNodes(bad_parent, divide, problem_node=node)

        top_tree = bad_parent.copy()
        self._filterTree(top_tree, nesting_filter=['bottom', 'problem'])
        middle_tree = bad_parent.copy()
        self._filterTree(middle_tree, nesting_filter=['top', 'bottom'])
        middle_tree = middle_tree.children[0]
        bottom_tree = bad_parent.copy()
        self._filterTree(bottom_tree, nesting_filter=['top', 'problem'])
        new_tree = [part for part in [top_tree, middle_tree, bottom_tree] if part != None]

        parent = bad_parent.parent
        parent.replaceChild(bad_parent, new_tree)
        self.report('moved', node, 'from', bad_parent)
        self._cleanUpMarks(parent)

        return SKIPNOW      


    def removeBrokenChildren(self, node):
        """Remove Nodes (while keeping their children) which can't be nested with their parents."""
        if node.__class__ in self.removeNodes.keys():
            if any([parent.__class__ in self.removeNodes[node.__class__] for parent in node.parents]):
                if node.children:
                    self.report('replaced child', node, node.children)
                    parent = node.parent
                    parent.replaceChild(node, newchildren=node.children)
                    self.insertDirtyNode(parent)
                    return SKIPNOW
                else:
                    self.report('removed child', node)
                    self.removeThis(node)
                    return SKIPNOW

    def _getNext(self, node): #FIXME: name collides with advtree.getNext
        if not (node.next or node.parent):
            return
        next = node.next or node.parent.next
        if next and not next.isblocknode:
            if not next.getAllDisplayText().strip():
                return self._getNext(next)
        return next

    def _getPrev(self, node): #FIXME: name collides with advtree.getPrev(ious)
        if not (node.previous or node.parent):
            return
        prev = node.previous or node.parent 
        if prev and not prev.isblocknode:
            if not prev.getAllDisplayText().strip():
                return self._getPrev(prev)
        return prev

    def _nextAdjacentNode(self, node):
        if node and node.next:
            res = node.next.getFirstLeaf() or node.next
            return res
        if node.parent:
            return self._nextAdjacentNode(node.parent)
        return None


    def removeBreakingReturns(self, node): 
        """Remove BreakingReturns that occur around blocknodes or as the first/last element inside a blocknode."""

        if node.isblocknode and node.parent:
            dirty = True
            changed = False
            while dirty:
                check_node = [node.getFirstLeaf(),
                             node.getLastLeaf(),
                             self._getNext(node),
                             self._getPrev(node)
                             ]
                check_node = set(check_node) # remove duplicates
                dirty = False
                for n in check_node:
                    if n.__class__ == BreakingReturn:
                        self.report('removing node', n)
                        n.parent.removeChild(n)
                        dirty = True
                        changed = True
            if changed:
                self.insertDirtyNode(node)

        if node.__class__ == BreakingReturn:
            next_node = self._nextAdjacentNode(node)
            if next_node.__class__ == BreakingReturn:
                self.removeThis(node)
                return SKIPNOW

    def removeDuplicateLinksInReferences(self, node):
        if node.__class__ == Reference and self.firstCheck(node):
            seen_targets = set()
            removed_link = False
            for link in [c for c in node.getAllChildren() if c.__class__ in [NamedURL, URL, ArticleLink]]:
                target = getattr(link, 'caption', None)
                if target:
                    if target in seen_targets:
                        self.report('removing duplicate link from reference', link)
                        link.parent.removeChild(link)
                        removed_link = True
                    else:
                        seen_targets.add(target)
            if removed_link:
                self.insertDirtyNode(node)
                return SKIPCHILDREN

            
    def filterChildren(self, node):
        if node.__class__ in self.nodeFilter and self.firstCheck(node):
            filter_list = [c for c in node.children if c.__class__ not in self.nodeFilter[node.__class__]]
            for n in filter_list:
                self.removeThis(n)
                self.report('filter child %s from parent %s' % (n, node))
            if filter_list:
                return SKIPNOW


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


    def buildDefinitionLists(self, node):
        if node.__class__ in [DefinitionTerm, DefinitionDescription]:
            if node.getChildNodesByClass(ItemList) or node.getParentNodesByClass(ItemList):
                return
            parent = node.getParent()
            if parent.__class__ == DefinitionList:
                return
            prev = node.getPrevious()
            if prev.__class__ == DefinitionList: 
                node.moveto(prev.getLastChild())
                self.report('moved node to prev. definition list')
            else: 
                dl = DefinitionList()
                parent.replaceChild(node, [dl])
                dl.appendChild(node)
                self.report('created new definition list')
            self.insertDirtyNode(parent)
                

    ################# DEBUG STUFF

    def fireAtWill(self, node):
        if node.__class__ == ItemList:
            node.vlist['fireAtWill'] = 'HIT'

    node_id = 0
    def setNodeIds(self, node):
        node.vlist['CID']= self.node_id
        self.node_id += 1
        for c in node.children:
            self.setNodeIds(c)
