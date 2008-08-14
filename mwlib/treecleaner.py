#! /usr/bin/env python
#! -*- coding:utf-8 -*-

# Copyright (c) 2007, PediaPress GmbH
# See README.txt for additional licensing information.

import copy

from advtree import buildAdvancedTree, AdvancedNode
from advtree import (Article, ArticleLink, BreakingReturn, CategoryLink, Cell, Chapter,
                     Cite, Code, Div, HorizontalRule, ImageLink, InterwikiLink, Item, ItemList,
                     LangLink, Link, Math, NamedURL, NamespaceLink, Paragraph, PreFormatted,
                     Reference, ReferenceList, Section, Source, SpecialLink, Table, Text, URL)


class TreeCleaner(object):

    """The TreeCleaner object cleans the parse tree to optimize writer ouput.

    All transformations should be lossless.

    """


    def __init__(self, tree):
        """Init with parsetree.

        If the parse tree is not an AdvancedTree this transformation is done by the TreeCleaner
        """

        if not isinstance(tree, AdvancedNode):
            buildAdvancedTree(tree)        
        self.tree = tree

        # list of nodes which do not require child nodes
        self.childlessOK = [Text, Cell, Link, Math, URL, BreakingReturn, HorizontalRule, CategoryLink,
                            Code, NamespaceLink, LangLink, SpecialLink, ImageLink, ReferenceList, Chapter,
                            NamedURL, ArticleLink, InterwikiLink]
       
        # keys are nodes, that are not allowed to be inside one of the nodes in the value-list
        # ex: we pull image links out of preformatted nodes and delete the preformatted node
        self.moveNodes = {ImageLink:[PreFormatted], ItemList:[Div],  Source:[PreFormatted]}
        
        # ex: we delete preformatted nodes which are inside reference nodes, we keep all children off the preformatted node 
        self.removeNodes = {PreFormatted:[Reference], Cite:[Item, Reference]}


    def clean(self, cleanerMethods):
        """Clean parse tree using cleaner methods in the methodList."""
        cleanerList = []
        for method in cleanerMethods:
            f = getattr(self, method, None)
            if f:
                cleanerList.append(f)
            else:
                raise 'TreeCleaner has no method: %r' % method            

        for child in self.tree.children:
            for cleaner in cleanerList:
                cleaner(child)

    def cleanAll(self):
        """Clean parse tree using all available cleaner methods."""

        cleanerMethods = ['_moveBrokenChildren',
                          '_removeChildlessNodes',
                          '_removeLangLinks',
                          '_fixLists',
                          '_removeSingleCellTables',
                          '_removeCriticalTables',
                          '_removeBrokenChildren',
                          '_fixTableColspans',
                          '_moveReferenceListSection']
        self.clean(cleanerMethods)


    def _fixLists(self, node): 
        """Removes paragraph nodes which only have a list as the only child - keeps the list."""
        if node.__class__ == ItemList and node.parent and node.parent.__class__ == Paragraph:
            if not node.siblings and node.parent.parent:
                node.parent.parent.replaceChild(node.parent,[node])        
        for c in node.children[:]:
            self._fixLists(c)

    def _removeChildlessNodes(self, node):
        """Remove nodes that have no children except for nodes in childlessOk list."""   

        if not node.children and node.__class__ not in self.childlessOK:
            removeNode = node
            while removeNode.parent and not removeNode.siblings:
                removeNode = removeNode.parent
            if removeNode.parent:
                removeNode.parent.removeChild(removeNode)

        for c in node.children[:]:
            self._removeChildlessNodes(c)

    def _removeLangLinks(self, node):
        """Removes the language links that are listed below an article.

        Language links inside the article should not be touched
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
            self._removeLangLinks(c)


    def _tableIsCrititcal(self, table):
        classAttr = table.attributes.get('class', '')
        if classAttr.find('navbox')>-1:    
            return True

        return False

    def _removeCriticalTables(self, node):
        """Remove problematic table nodes - keep content.
        
        Table rendering is limited: a single cell, in many writers, can never be larger than a single page,
        otherwise rendering fails. In this method problematic tables are removed.
        The content is preserved if possible and only the outmost 'container' table is removed.
        """

        if node.__class__ == Table and self._tableIsCrititcal(node):
            children = []
            for row in node.children:
                for cell in row:
                    for n in cell:
                        children.append(n)
            if node.parent:
                node.parent.replaceChild(node, children)
            return

        for c in node.children:
            self._removeCriticalTables(c)

    def _fixTableColspans(self, node):
        """ Fix erronous colspanning information in table nodes.

        1. SINGLE CELL COLSPAN: if a row contains a single cell, the
           colspanning amount is limited to the maximum table width
        """

        # SINGLE CELL COLSPAN 
        if node.__class__ == Table:
            maxwidth = 0
            for row in node.children:
                numCells = len(row.children)
                rowwidth = 0
                for cell in row.children:
                    colspan = cell.attributes.get('colspan', 1)
                    if numCells > 1:
                        rowwidth += colspan
                    else:
                        rowwidth += 1
                maxwidth = max(maxwidth,  rowwidth)
            for row in node.children:
                numCells = len(row.children)
                if numCells == 1:
                    cell = row.children[0]
                    colspan = cell.attributes.get('colspan', 1)
                    if colspan and colspan > maxwidth:
                        cell.vlist['colspan'] = maxwidth
        # /SINGLE CELL COLSPAN
        for c in node.children:
            self._fixTableColspans(c)

    def _any(self, list):
        for x in list:
            if x:
                return True
        return False

    def _removeBrokenChildren(self, node):
        """Remove Nodes (while keeping their children) which can't be nested with their parents."""
        if node.__class__ in self.removeNodes.keys():
            if self._any([parent.__class__ in self.removeNodes[node.__class__] for parent in node.parents]):
                if node.children:
                    children = node.children
                    node.parent.replaceChild(node, newchildren=children)
                else:
                    node.parent.removeChild(node)
                return

        for c in node.children:
            self._removeBrokenChildren(c)


    def _moveBrokenChildren(self, node):
        """Move child nodes to their parents level, if they can't be nested with their parents."""

        if node.__class__ in self.moveNodes.keys():
            firstContainer = node.parent
            container = node.parent
            while container:
                if container.__class__ in self.moveNodes[node.__class__]:
                    if container.parent:
                        node.moveto(container)
                container = container.parent

        for c in node.children:
            self._moveBrokenChildren(c)


    def _removeSingleCellTables(self, node):
        """Remove table nodes which contain only a single row with a single cell"""

        if node.__class__ == Table:
            if len(node.children) == 1 and len(node.children[0].children) == 1:
                if node.parent:
                    cell_content = node.children[0].children[0].children
                    node.parent.replaceChild(node, cell_content)

        for c in node.children:
            self._removeSingleCellTables(c)


    def _moveReferenceListSection(self, node):
        """Move the section containing the reference list to the end of the article."""

        if node.__class__ == Article:
            sections = node.getChildNodesByClass(Section)
            for section in sections:
                reflists = section.getChildNodesByClass(ReferenceList)
                if reflists and section.parent:
                    section.parent.removeChild(section)
                    node.appendChild(section)
            return

        for c in node.children:
            self._moveReferenceListSection(c)

    # FIXME: replace this by implementing and using getParentStyleInfo(style='blub') where parent styles are needed
    def _inheritStyles(self, node, inheritStyle={}):
        """style information is handed down to child nodes."""

        def flattenStyle(styleHash):
            res =  {}
            for k,v in styleHash.items():
                if isinstance(v,dict):
                    for _k,_v in v.items():
                        if isinstance(_v, basestring):
                            res[_k.lower()] = _v.lower() 
                        else:
                            res[_k.lower()]= _v
                else:
                    if isinstance(v, basestring):
                        res[k.lower()] = v.lower() 
                    else:
                        res[k.lower()] = v
            return res

        def cleanInheritStyles(styleHash):
            sh = copy.copy(styleHash)
            ignoreStyles = ['border', 'border-spacing', 'background-color', 'background', 'class', 'margin', 'padding', 'align', 'colspan', 'rowspan',
                            'empty-cells', 'rules', 'clear', 'float', 'cellspacing', 'display', 'visibility']
            for style in ignoreStyles:
                sh.pop(style, None)
            return sh

        style = getattr(node, 'vlist', {})
        nodeStyle = inheritStyle
        if style:
            nodeStyle.update(flattenStyle(style))
            node.vlist = nodeStyle        
        elif inheritStyle:
            node.vlist = nodeStyle
        else:
            nodeStyle = {}

        for c in node.children:
            _is = cleanInheritStyles(nodeStyle)
            self._inheritStyles(c, inheritStyle=_is)
