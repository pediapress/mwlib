#! /usr/bin/env python

# Copyright (c) 2007-2009 PediaPress GmbH
# See README.txt for additional licensing information.

import re
import sys

import _mwscan
import htmlentitydefs

from mwlib.parser import paramrx


class Token:
    t_end = 0
    t_text = 1
    t_entity = 2
    t_special = 3
    t_magicword = 4
    t_comment = 5
    t_2box_open = 6
    t_2box_close = 7
    t_http_url = 8
    t_break = 9
    t_begin_table = 10
    t_end_table = 11
    t_html_tag = 12
    t_singlequote = 13
    t_pre = 14
    t_section = 15
    t_section_end = 16
    t_item = 17
    t_colon = 18
    t_semicolon = 19
    t_hrule = 20
    t_newline = 21
    t_column = 22
    t_row = 23
    t_tablecaption = 24
    t_urllink = 25

    token2name = {}


for directory in dir(Token):
    token2name = Token.token2name
    if directory.startswith("t_"):
        token2name[getattr(Token, directory)] = directory
else:
    del directory


def _split_tag(txt):
    matched_tag = re.match(r" *(\w+)(.*)", txt)
    if matched_tag is None:
        raise ValueError("could not match tag name")
    name = matched_tag.group(1)
    values = matched_tag.group(2)
    return name, values


def dump_tokens(text, tokens):
    for token_type, start, length in tokens:
        print(token_type, repr(text[start: start + length]))


def scan(text):
    text += "\0" * 32
    tokens = _mwscan.scan(text)
    return ScanResult(text, tokens)


def resolve_entity(entity):
    if entity[1] == "#":
        try:
            if entity[2] == "x" or entity[2] == "X":
                return chr(int(entity[3:-1], 16))
            return chr(int(entity[2:-1]))
        except ValueError:
            return entity
    else:
        try:
            return chr(htmlentitydefs.name2codepoint[entity[1:-1]])
        except KeyError:
            return entity


class ScanResult:
    def __init__(self, source, toks):
        self.source = source
        self.toks = toks

    def rawtext(self, token):
        (_, start, tlen) = token
        return self.source[start: start + tlen]

    def text(self, token):
        raw_text = self.rawtext(token)
        if token[0] == Token.t_entity:
            return resolve_entity(raw_text)
        return raw_text

    def dump(self, out=None):
        if out is None:
            out = sys.stdout
        for token in self:
            out.write("%s\n" % self.repr(token))

    def repr(self, token):
        return f"({Token.token2name.get(token[0])}, {self.rawtext(token)!r})"

    def __len__(self):
        return len(self.toks)

    def __iter__(self):
        return iter(self.toks)

    def __getitem__(self, idx):
        return self.toks[idx]


class _CompatScanner:
    from mwlib.tagext import default_registry as tagextensions

    allowed_tags = None

    class Ignore:
        pass

    tok2compat = {
        Token.t_text: "TEXT",
        Token.t_special: "SPECIAL",
        Token.t_2box_open: "[[",
        Token.t_2box_close: "]]",
        Token.t_http_url: "URL",
        Token.t_break: "BREAK",
        Token.t_singlequote: "SINGLEQUOTE",
        Token.t_pre: "PRE",
        Token.t_section: "SECTION",
        Token.t_section_end: "ENDSECTION",
        Token.t_magicword: Ignore,
        Token.t_comment: Ignore,
        Token.t_end: Ignore,
        Token.t_item: "ITEM",
        Token.t_colon: "EOLSTYLE",
        Token.t_semicolon: "EOLSTYLE",
        Token.t_newline: "\n",
        Token.t_begin_table: "BEGINTABLE",
        Token.t_end_table: "ENDTABLE",
        Token.t_column: "COLUMN",
        Token.t_row: "ROW",
        Token.t_tablecaption: "TABLECAPTION",
        Token.t_urllink: "URLLINK",
    }

    def _init_allowed_tags(self):
        from mwlib.parser import _get_tags

        self.allowed_tags = _get_tags()

    def __call__(self, text):
        if self.allowed_tags is None:
            self._init_allowed_tags()

        tokens = scan(text)
        scanres = ScanResult(text, tokens)

        res = []

        def get_substring():
            return text[start: start + tlen]

        def append_to_result(token_type):
            return res.append((token_type, get_substring()))

        ignore = self.ignore
        tok2compat = self.tok2compat

        i = 0
        numtokens = len(tokens)
        while i < numtokens:
            token_type, start, tlen = tokens[i]
            n = tok2compat.get(token_type)
            if n is ignore:
                i += 1
                continue
            elif n is not None:
                append_to_result(n)
            elif token_type == Token.t_entity:
                res.append(("TEXT", resolve_entity(get_substring())))
            elif token_type == Token.t_hrule:
                res.append((self.tagtoken("<hr />"), get_substring()))
            elif token_type == Token.t_html_tag:
                substr = get_substring()

                tag_token = self.tagtoken(substr)
                is_end_token = isinstance(tag_token, EndTagToken)
                closing_or_self_closing = is_end_token or tag_token.self_closing

                if tag_token.t in self.tagextensions or tag_token.t in ("imagemap", "gallery"):
                    if closing_or_self_closing:
                        i += 1
                        continue
                    tagname = tag_token.t

                    res.append((tag_token, substr))
                    i += 1
                    text_start = None
                    text_end = None
                    end_token = None

                    while i < numtokens:
                        token_type, start, tlen = tokens[i]
                        if text_start is None:
                            text_start = start

                        if token_type == Token.t_html_tag:
                            tag_token = self.tagtoken(get_substring())
                            if tag_token.t == tagname:
                                end_token = (tag_token, get_substring())
                                break
                        text_end = start + tlen

                        i += 1

                    if text_end:
                        res.append(("TEXT", text[text_start:text_end]))

                    if end_token:
                        res.append(end_token)

                elif tag_token.t == "nowiki":
                    i += 1
                    if is_end_token or tag_token.self_closing:
                        continue
                    while i < numtokens:
                        token_type, start, tlen = tokens[i]
                        if token_type == Token.t_html_tag:
                            tag_token = self.tagtoken(get_substring())
                            if tag_token.t == "nowiki":
                                break
                        res.append(("TEXT", scanres.text((token_type,
                                                          start, tlen))))
                        i += 1
                elif tag_token.t == "table":
                    if is_end_token:
                        res.append(("ENDTABLE", get_substring()))
                    else:
                        res.append(("BEGINTABLE", get_substring()))
                elif tag_token.t in ["th", "td"]:
                    if not is_end_token:
                        res.append(("COLUMN", get_substring()))
                elif tag_token.t == "tr":
                    if not is_end_token:
                        res.append(("ROW", get_substring()))
                else:
                    if tag_token.t in self.allowed_tags:
                        res.append((tag_token, substr))
                    else:
                        res.append(("TEXT", substr))
            else:
                append_to_result(type)
            i += 1

        return res

    def tagtoken(self, text):
        self_closing = False
        if text.startswith("</"):
            name = text[2:-1]
            klass = EndTagToken
        elif text.endswith("/>"):
            name = text[1:-2]
            klass = TagToken
            self_closing = True
        else:
            name = text[1:-1]
            klass = TagToken

        name, values = _split_tag(name)

        values = dict(paramrx.findall(values))
        name = name.lower()

        if name in ['br', 'references']:
            klass = TagToken

        result = klass(name, text)
        result.self_closing = self_closing
        result.values = values
        return result


compat_scan = _CompatScanner()


class _BaseTagToken:
    def __eq__(self, other):
        if isinstance(other, str):
            return self.token == other
        if isinstance(other, self.__class__):
            return self.token == other.token
        return False

    def __ne__(self, other):
        return self != other

    def __hash__(self):
        return hash(self.token)


class TagToken(_BaseTagToken):
    values = {}
    self_closing = False

    def __init__(self, token, text=""):
        self.token = token
        self.text = text

    def __repr__(self):
        return f"<Tag:{self.token!r} {self.text!r}>"


class EndTagToken(_BaseTagToken):
    def __init__(self, token, text=""):
        self.token = token
        self.text = text

    def __repr__(self):
        return f"<EndTag:{self.token!r}>"


def tokenize(token_input):
    if token_input is None:
        raise ValueError("must specify input argument in tokenize")
    return compat_scan(token_input)
