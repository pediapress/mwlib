#! /usr/bin/env python

# Copyright (c) 2007-2009 PediaPress GmbH
# See README.txt for additional licensing information.

import os
import re

from mwlib.log import Log
from mwlib import namespace
from mwlib.refine.util import ImageMod

log = Log("parser")

        
def show(out, node, indent=0, verbose=False):
    if verbose:
        print >>out, "    "*indent, node, repr(getattr(node, 'vlist', ''))
    else:
        print >>out, "    "*indent, node
    for x in node:
        show(out, x, indent+1, verbose=verbose)


paramrx = re.compile("(?P<name>\w+) *= *(?P<value>(?:(?:\".*?\")|(?:\'.*?\')|(?:(?:\w|[%:])+)))")
def parseParams(s):
    def style2dict(s):
        res = {}
        for x in s.split(';'):
            if ':' in x:
                var, value = x.split(':', 1)
                var = var.strip().lower()
                value = value.strip()
                res[var] = value

        return res
    
    def maybeInt(v):
        try:
            return int(v)
        except:
            return v
    
    r = {}
    for name, value in paramrx.findall(s):
        if value.startswith('"') or value.startswith("'"):
            value = value[1:-1]
            
        if name.lower() == 'style':
            value = style2dict(value)
            r['style'] = value
        else:
            r[name] = maybeInt(value)
    return r

from mwlib.parser.nodes import (Node, Math, Ref, Item, ItemList, Style, 
                                Book, Chapter, Article, Paragraph, Section,
                                Timeline, TagNode, PreFormatted, URL, NamedURL,
                                _VListNode, Table, Row, Cell, Caption, Link, ArticleLink, SpecialLink,
                                NamespaceLink, InterwikiLink, LangLink, CategoryLink, ImageLink, Text, Control)
