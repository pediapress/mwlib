# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing informationodes.

from mwlib import nshandling
from mwlib.parser import nodes
from mwlib.refine import core
from mwlib.token.utoken import Token

token2class = {
    Token.t_complex_table: nodes.Table,
    Token.t_complex_caption: nodes.Caption,
    Token.t_complex_table_row: nodes.Row,
    Token.t_complex_table_cell: nodes.Cell,
    Token.t_complex_link: nodes.Link,
    Token.t_complex_section: nodes.Section,
    Token.t_complex_article: nodes.Article,
    Token.t_complex_tag: nodes.TagNode,
    Token.t_complex_named_url: nodes.NamedURL,
    Token.t_complex_style: nodes.Style,
    Token.t_complex_node: nodes.Node,
    Token.t_complex_line: nodes.Node,
    Token.t_http_url: nodes.URL,
    Token.t_complex_preformatted: nodes.PreFormatted,
}


def _handle_node_type_t_http_url(node) -> bool:
    node.caption = node.text
    node.children = []
    return False


def _handle_node_type_t_complex_compat(node) -> bool:
    node.__class__ = node.compatnode.__class__
    node.__dict__ = node.compatnode.__dict__
    return True


def _handle_node_type_t_magicword(node) -> bool:
    node.caption = ""
    node.children = []
    node.__class__ = nodes.Text
    return True


def _handle_node_type_t_html_tag_end(node) -> bool:
    return _handle_node_type_t_magicword(node)


def _lookup_handler_function(node):
    handlers = {
        Token.t_http_url: _handle_node_type_t_http_url,
        Token.t_complex_compat: _handle_node_type_t_complex_compat,
        Token.t_magicword: _handle_node_type_t_magicword,
        Token.t_html_tag_end: _handle_node_type_t_html_tag_end,
    }
    if node.type == Token.t_complex_table and node.children:
        node.children = [
            x
            for x in node.children
            if x.type in (Token.t_complex_table_row, Token.t_complex_caption)
            or x.tagname == "caption"
        ]
    elif node.type == Token.t_complex_table_row and node.children:
        node.children = [x for x in node.children if x.type == Token.t_complex_table_cell]
    return handlers


def _handle_link_node(node):
    ns_handler = node.ns
    if node.colon:
        ns_handler = nshandling.NS_SPECIAL
    if ns_handler == nshandling.NS_IMAGE:
        node.__class__ = nodes.ImageLink
    elif ns_handler == nshandling.NS_MAIN:
        node.__class__ = nodes.ArticleLink
    elif ns_handler == nshandling.NS_CATEGORY:
        node.__class__ = nodes.CategoryLink
    elif ns_handler is not None:
        node.__class__ = nodes.NamespaceLink
    elif node.langlink:
        node.__class__ = nodes.LangLink
        node.namespace = node.target.split(":", 1)[0]
    elif node.interwiki:
        node.__class__ = nodes.InterwikiLink
        node.namespace = node.interwiki
    if node.namespace is None:
        node.namespace = node.ns


def _set_nodex_class_and_caption(node):
    node_types = {
        (Token.t_hrule, None): ("hr", nodes.TagNode),
        (Token.t_html_tag, "hr"): ("hr", nodes.TagNode),
        (Token.t_html_tag_end, "hr"): ("hr", nodes.TagNode),
        (None, "br"): ("br", nodes.TagNode),
        (Token.t_complex_style, None): (None, nodes.Style),
    }
    for (node_type, tag_name), (caption, klass) in node_types.items():
        if (node_type is None or node.type == node_type) and (
            tag_name is None or node.rawtagname == tag_name
        ):
            node.__class__ = klass
            node.caption = caption if caption is not None else node.caption
    if node.__class__ == nodes.Text:
        node.caption = node.text or ""
        if node.children:
            raise ValueError(f"{node!r} has children")
    if node.children is None:
        node.children = []
    if node.vlist is None:
        node.vlist = {}


def _handle_complex_node_type(node: nodes.Node):
    node.caption = node.tagname
    timeline = node.timeline if hasattr(node, "timeline") else None
    math = node.math if hasattr(node, "math") else None

    tag_classes = {
        "p": nodes.Paragraph,
        "caption": nodes.Caption,
        "ul": nodes.ItemList,
        "ol": nodes.ItemList,
        "li": nodes.Item,
        "timeline": nodes.Timeline,
        "math": nodes.Math,
        "b": nodes.Style,
        "strong": nodes.Style,
        "pre": nodes.PreFormatted,
        "blockquote": nodes.Style,
        "cite": nodes.Style,
        "big": nodes.Style,
        "small": nodes.Style,
        "s": nodes.Style,
        "var": nodes.Style,
        "i": nodes.Style,
        "em": nodes.Style,
        "sup": nodes.Style,
        "sub": nodes.Style,
        "u": nodes.Style,
    }
    tag_captions = {
        "timeline": timeline,
        "math": math,
        "b": "'''",
        "strong": "'''",
        "blockquote": "-",
        "cite": "cite",
        "big": "big",
        "small": "small",
        "s": "s",
        "var": "var",
        "i": "''",
        "em": "''",
        "sup": "sup",
        "sub": "sub",
        "u": "u",
    }

    if node.tagname in tag_classes:
        node.__class__ = tag_classes[node.tagname]
        node.caption = tag_captions.get(node.tagname, node.tagname)

    if node.tagname == "ref":
        # don't do anything here, we will handle this later
        pass
    elif node.tagname == "ol":
        node.numbered = True
    elif (
        node.tagname == "imagemap"
        and hasattr(node.imagemap, "imagelink")
        and node.imagemap.imagelink
    ):
        _change_classes(node.imagemap.imagelink)


def _set_caption_and_check_children(node):
    node.caption = node.text or ""
    if node.children:
        raise ValueError(f"{node!r} has children")


def _change_classes(node):
    if isinstance(node, Token):
        handlers = _lookup_handler_function(node)

        return_after_handler = False

        handler_func = handlers.get(node.type)
        if handler_func:
            return_after_handler = handler_func(node)

        if return_after_handler:
            return

        klass = token2class.get(node.type, nodes.Text)

        if klass == nodes.Text:
            _set_caption_and_check_children(node)

        node.__class__ = klass

        _set_nodex_class_and_caption(node)

        if node.type == Token.t_complex_tag:
            _handle_complex_node_type(node)

        if node.__class__ == nodes.Link:
            _handle_link_node(node)

        node = node.children

    if node:
        for child in node:
            _change_classes(child)


def parse_txt(raw, **kwargs):
    sub = core.parse_txt(raw, **kwargs)
    article = Token(type=Token.t_complex_article, start=0, len=0, children=sub)
    _change_classes(article)
    return article
