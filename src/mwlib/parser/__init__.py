#! /usr/bin/env python

# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.


from mwlib.utilities.log import Log
from mwlib.parser.nodes import (
    URL,
    Article,
    ArticleLink,
    Book,
    Caption,
    CategoryLink,
    Cell,
    Chapter,
    Control,
    ImageLink,
    InterwikiLink,
    Item,
    ItemList,
    LangLink,
    Link,
    Math,
    NamedURL,
    NamespaceLink,
    Node,
    Paragraph,
    PreFormatted,
    Ref,
    Row,
    Section,
    SpecialLink,
    Style,
    Table,
    TagNode,
    Text,
    Timeline,
)

log = Log("parser")


def show(out, node, indent=0, verbose=False):
    if verbose:
        log.debug(("parser:show    " * indent) + f"{node} {repr(getattr(node, 'vlist', ''))}")
    else:
        log.info(("parser:show    " * indent) + str(node))
    for child in node:
        show(out, child, indent + 1, verbose=verbose)

def build_amap():
    return {
        Text: "caption",
        Link: "target",
        URL: "caption",
        Math: "caption",
    }
