#! /usr/bin/env python

# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

# unified/universal token

import sys
from typing import Optional

from mwlib.parser.refine.util import parse_params, resolve_entity
from mwlib.parser.token import _uscan as _mwscan
from mwlib.parser.token.token import Token as BaseToken
from mwlib.utils.unorganized import split_tag


def walk_children(children, filt):
    for child in children:
        yield from walknode(child, filt)


def walknode(node, filt=lambda _: True):
    if not isinstance(node, Token):
        yield from walk_children(node, filt)
        return

    if filt(node):
        yield node

    if node.children:
        yield from walk_children(node.children, filt)


def walknodel(node, filt=lambda x: True):
    return list(walknode(node, filt=filt))


def show(node, out=None, indent=0, verbose=False):
    if node is None:
        return

    if out is None:
        out = sys.stdout

    if not isinstance(node, Token):
        for child in node:
            show(child, out=out, indent=indent, verbose=verbose)
        return

    out.write("{}{!r}\n".format("    " * indent, node))

    children = node.children
    if children:
        for child in children:
            show(child, out=out, indent=indent + 1, verbose=verbose)


class _Show:
    def __get__(self, obj, type=None):
        if obj is None:
            return lambda node, out=None: show(node, out=out)
        else:
            return lambda out=None: show(obj, out=out)


class Token(BaseToken):
    caption = ""
    vlist = None
    target = None
    level = None
    children: list | None = None
    target: str | None = None
    full_target = None

    rawtagname = None
    tagname = None
    ns = None
    lineprefix = None
    interwiki = None
    langlink = None
    namespace = None
    blocknode = False

    # image attributes
    align = None
    thumb = False
    frame = None

    t_complex_article = None
    t_complex_caption = None
    t_complex_compat = None
    t_complex_line = None
    t_complex_link = None
    t_complex_named_url = None
    t_complex_node = None
    t_complex_preformatted = None
    t_complex_section = None
    t_complex_style = None
    t_complex_table = None
    t_complex_table_cell = None
    t_complex_table_row = None
    t_complex_tag = None

    _text = None

    @staticmethod
    def join_as_text(tokens):
        return "".join([x.text or "" for x in tokens])

    def _get_text(self):
        if self._text is None and self.source is not None:
            self._text = self.source[self.start: self.start + self.len]
        return self._text

    def _set_text(self, text):
        self._text = text

    text = property(_get_text, _set_text)

    def __init__(self, type=None, start=None, len=None,
                 source=None, text=None, **kw):
        self.type = type
        self.start = start
        self.len = len
        self.source = source
        if text is not None:
            self.text = text

        self.__dict__.update(kw)

    def __repr__(self):
        if isinstance(self, Token):
            repr_elements = [self.token2name.get(self.type, self.type)]
        else:
            repr_elements = [self.__class__.__name__]
        if self.text is not None:
            repr_elements.append(repr(self.text)[1:])
        if self.tagname:
            repr_elements.append(" tagname=")
            repr_elements.append(repr(self.tagname))
        if self.rawtagname:
            repr_elements.append(" rawtagname=")
            repr_elements.append(repr(self.rawtagname))

        if self.vlist:
            repr_elements.append(" vlist=")
            repr_elements.append(repr(self.vlist))
        if self.target:
            repr_elements.append(" target=")
            repr_elements.append(repr(self.target))
        if self.level:
            repr_elements.append(" level=")
            repr_elements.append(repr(self.level))
        if self.ns is not None:
            repr_elements.append(" ns=")
            repr_elements.append(repr(self.ns))
        if self.lineprefix is not None:
            repr_elements.append(" lineprefix=")
            repr_elements.append(self.lineprefix)
        if self.interwiki:
            repr_elements.append(" interwiki=")
            repr_elements.append(repr(self.interwiki))
        if self.langlink:
            repr_elements.append(" langlink=")
            repr_elements.append(repr(self.langlink))
        if self.type == self.t_complex_style:
            repr_elements.append(repr(self.caption))
        elif self.caption:
            repr_elements.append("->")
            repr_elements.append(repr(self.caption))

        return "".join(repr_elements)

    show = _Show()


token2name = Token.token2name
for directory in dir(Token):
    if directory.startswith("t_"):
        token2name[getattr(Token, directory)] = directory
del directory, token2name

def _analyze_html_tag(tag):
    text = tag.text
    self_closing = False
    if text.startswith("</"):
        name = text[2:-1]
        is_end_token = True
    elif text.endswith("/>"):
        name = text[1:-2]
        self_closing = True
        is_end_token = False  # ???
    else:
        name = text[1:-1]
        is_end_token = False

    name, values = split_tag(name)
    tag.vlist = parse_params(values)
    name = name.lower()

    if name == "br":
        is_end_token = False

    tag.rawtagname = name
    tag.tag_selfClosing = self_closing
    tag.tag_isEndToken = is_end_token
    if is_end_token:
        tag.type = tag.t_html_tag_end


def dump_tokens(text, tokens):
    for type, start, len in tokens:
        print(type, repr(text[start: start + len]))


def scan(text):
    text += "\0" * 32
    return _mwscan.scan(text)


class CompatScanner:
    allowed_tags = None

    def _init_allowed_tags(self):
        self.allowed_tags = set(
            ["abbr", "b", "big", "blockquote", "br", "center", "cite", "code", "del", "div", "em", "endfeed", "font", "h1", "h2", "h3", "h4", "h5", "h6", "hr", "i", "index", "inputbox", "ins", "kbd", "li", "ol", "p", "pages", "references", "rss", "s", "small", "span", "startfeed", "strike", "strong", "sub", "sup", "caption", "table", "td", "th", "tr", "tt", "u", "ul", "var", "dl", "dt", "dd", "mapframe"]
        )

    def _get_substring(self, text, start, token_length):
        return text[start: start + token_length]

    def _append_colon_tokens(self, text, start, token_length,
                             res: list[Token]):
        txt = self._get_substring(text, start, token_length)
        count = txt.count(":")
        if count:
            res.append(Token(type=Token.t_colon,
                             start=start, len=count, source=text))
        token_length -= count
        start += count

        return start, token_length

    def _process_and_append_html_token(self, text, start, token_length,
                                       res: list[Token], token,
                                       uniquifier=None):
        sub_str = self._get_substring(text, start, token_length)
        if uniquifier:
            sub_str = uniquifier.replace_uniq(sub_str)
            token.text = sub_str
        _analyze_html_tag(token)
        tagname = token.rawtagname
        if tagname in self.allowed_tags:
            res.append(token)
        else:
            res.append(Token(type=Token.t_text, start=start,
                             len=token_length, source=text))

    def __call__(self, text, uniquifier=None):
        if self.allowed_tags is None:
            self._init_allowed_tags()

        tokens = scan(text)

        res = []

        for type, start, token_length in tokens:
            if type == Token.t_begin_table:
                start, token_length = self._append_colon_tokens(text, start,
                                                                token_length,
                                                                res)

            token = Token(type=type, start=start, len=token_length,
                          source=text)

            if type == Token.t_entity:
                token.text = resolve_entity(self._get_substring(text, start,
                                                                token_length))
                token.type = Token.t_text
                res.append(token)
            elif type == Token.t_html_tag:
                self._process_and_append_html_token(text, start, token_length,
                                                    res, token,
                                                    uniquifier=uniquifier)
            else:
                res.append(token)

        return res


compat_scan = CompatScanner()


def tokenize(input_arg, uniquifier=None):
    if not input_arg:
        raise ValueError("must specify input argument in tokenize")
    return compat_scan(input_arg, uniquifier=uniquifier)
