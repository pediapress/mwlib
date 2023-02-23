# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

from __future__ import absolute_import

from mwlib import nshandling
from mwlib.parser import nodes as n
from mwlib.refine import core
from mwlib.utoken import Token as T

tok2class = {
    T.t_complex_table: n.Table,
    T.t_complex_caption: n.Caption,
    T.t_complex_table_row: n.Row,
    T.t_complex_table_cell: n.Cell,
    T.t_complex_link: n.Link,
    T.t_complex_section: n.Section,
    T.t_complex_article: n.Article,
    T.t_complex_tag: n.TagNode,
    T.t_complex_named_url: n.NamedURL,
    T.t_complex_style: n.Style,
    T.t_complex_node: n.Node,
    T.t_complex_line: n.Node,
    T.t_http_url: n.URL,
    T.t_complex_preformatted: n.PreFormatted,
}


def _change_classes(node):
    if isinstance(node, T):
        if node.type == T.t_complex_table and node.children:
            node.children = [
                x
                for x in node.children
                if x.type in (T.t_complex_table_row, T.t_complex_caption) or x.tagname == "caption"
            ]
        elif node.type == T.t_complex_table_row and node.children:
            node.children = [x for x in node.children if x.type == T.t_complex_table_cell]

        if node.type == T.t_http_url:
            node.caption = node.text
            node.children = []

        if node.type == T.t_complex_compat:
            node.__class__ = node.compatnode.__class__
            node.__dict__ = node.compatnode.__dict__
            return

        if node.type == T.t_magicword:
            node.caption = u""
            node.children = []
            node.__class__ = n.Text
            return

        if node.type == T.t_html_tag_end:
            node.caption = u""
            node.children = []
            node.__class__ = n.Text
            return

        klass = tok2class.get(node.type, n.Text)

        if klass == n.Text:
            node.caption = node.text or u""
            assert not node.children, "%r has children" % (node,)

        node.__class__ = klass

        if node.type == T.t_hrule or (
            node.type in (T.t_html_tag, T.t_html_tag_end) and node.rawtagname == "hr"
        ):
            node.__class__ = n.TagNode
            node.caption = "hr"

        if node.rawtagname == "br":
            node.__class__ = n.TagNode
            node.caption = "br"

        if node.type == T.t_complex_style:
            node.__class__ = n.Style

        if node.__class__ == n.Text:
            node.caption = node.text or u""
            assert not node.children, "%r has children" % (node,)

        if node.children is None:
            node.children = []

        if node.vlist is None:
            node.vlist = {}
        if node.type == T.t_complex_tag:
            node.caption = node.tagname
            if node.tagname == "p":
                node.__class__ = n.Paragraph
            elif node.tagname == "caption":
                node.__class__ = n.Caption
            elif node.tagname == "ref":
                pass
                # node.__class__=N.Ref
            elif node.tagname == "ul":
                node.__class__ = n.ItemList
            elif node.tagname == "ol":
                node.__class__ = n.ItemList
                node.numbered = True
            elif node.tagname == "li":
                node.__class__ = n.Item
            elif node.tagname == "timeline":
                node.__class__ = n.Timeline
                node.caption = node.timeline
            elif node.tagname == "imagemap":
                if hasattr(node.imagemap, "imagelink") and node.imagemap.imagelink:
                    _change_classes(node.imagemap.imagelink)
            elif node.tagname == "math":
                node.__class__ = n.Math
                node.caption = node.math
            elif node.tagname == "b":
                node.__class__ = n.Style
                node.caption = "'''"
            elif node.tagname == "pre":
                node.__class__ = n.PreFormatted
            elif node.tagname == "blockquote":
                node.__class__ = n.Style
                node.caption = "-"
            elif node.tagname == "strong":
                node.__class__ = n.Style
                node.caption = "'''"
            elif node.tagname == "cite":
                node.__class__ = n.Style
                node.caption = "cite"
            elif node.tagname == "big":
                node.__class__ = n.Style
                node.caption = "big"
            elif node.tagname == "small":
                node.__class__ = n.Style
                node.caption = "small"
            elif node.tagname == "s":
                node.__class__ = n.Style
                node.caption = "s"
            elif node.tagname == "var":
                node.__class__ = n.Style
                node.caption = "var"
            elif node.tagname == "i":
                node.__class__ = n.Style
                node.caption = "''"
            elif node.tagname == "em":
                node.__class__ = n.Style
                node.caption = "''"
            elif node.tagname == "sup":
                node.__class__ = n.Style
                node.caption = "sup"
            elif node.tagname == "sub":
                node.__class__ = n.Style
                node.caption = "sub"
            elif node.tagname == "u":
                node.__class__ = n.Style
                node.caption == "u"

        if node.__class__ == n.Link:
            ns = node.ns

            if node.colon:
                ns = nshandling.NS_SPECIAL

            if ns == nshandling.NS_IMAGE:
                node.__class__ = n.ImageLink
            elif ns == nshandling.NS_MAIN:
                node.__class__ = n.ArticleLink
            elif ns == nshandling.NS_CATEGORY:
                node.__class__ = n.CategoryLink
            elif ns is not None:
                node.__class__ = n.NamespaceLink
            elif node.langlink:
                node.__class__ = n.LangLink
                node.namespace = node.target.split(":", 1)[0]
            elif node.interwiki:
                node.__class__ = n.InterwikiLink
                node.namespace = node.interwiki

            ns, partial, full = node.nshandler.splitname(node.target)
            if node.namespace is None:
                node.namespace = node.ns

        node = node.children

    if node:
        for x in node:
            _change_classes(x)


def parse_txt(raw, **kwargs):
    sub = core.parse_txt(raw, **kwargs)
    article = T(type=T.t_complex_article, start=0, len=0, children=sub)
    _change_classes(article)
    return article
