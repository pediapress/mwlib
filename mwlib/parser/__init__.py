#! /usr/bin/env python

# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.


from mwlib.log import Log

log = Log("parser")

        
def show(out, node, indent=0, verbose=False):
    if verbose:
        print >>out, "    "*indent, node, repr(getattr(node, 'vlist', ''))
    else:
        print >>out, "    "*indent, node
    for x in node:
        show(out, x, indent+1, verbose=verbose)

from mwlib.parser.nodes import (Node, Math, Ref, Item, ItemList, Style, 
                                Book, Chapter, Article, Paragraph, Section,
                                Timeline, TagNode, PreFormatted, URL, NamedURL,
                                Table, Row, Cell, Caption, Link, ArticleLink, SpecialLink,
                                NamespaceLink, InterwikiLink, LangLink, CategoryLink, ImageLink, Text, Control)
