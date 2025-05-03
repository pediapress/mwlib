#! /usr/bin/env python
# -*- compile-command: "../../tests/test_refine.py" -*-

# Copyright (c) 2007-2023 PediaPress GmbH
# See README.rst for additional licensing information.
import logging
from typing import Any, Optional

from mwlib.core import nshandling
from mwlib.extensions import imgmap
from mwlib.parser import styleanalyzer, tagext
from mwlib.parser.refine import util
from mwlib.parser.refine.parse_table import TableFixer, TableGarbageRemover, TableParser
from mwlib.parser.refine.tagparser import TagParser
from mwlib.parser.token.utoken import Token, tokenize
from mwlib.utils import uniq

try:
    from mwlib.parser.refine import _core
except ImportError:
    _core = None

log = logging.getLogger(__name__)

Token.t_complex_table = "complex_table"
Token.t_complex_caption = "complex_caption"
Token.t_complex_table_row = "complex_table_row"
Token.t_complex_table_cell = "complex_table_cell"
Token.t_complex_tag = "complex_tag"
Token.t_complex_link = "link"
Token.t_complex_section = "section"
Token.t_complex_article = "article"
Token.t_complex_indent = "indent"
Token.t_complex_line = "line"
Token.t_complex_named_url = "named_url"
Token.t_complex_style = "style"
Token.t_complex_node = "node"
Token.t_complex_preformatted = "preformatted"
Token.t_complex_compat = "compat"
Token.t_vlist = "vlist"

Token.children = None


if _core is not None:
    get_token_walker = _core.TokenWalker
else:

    def get_token_walker(skip_tags=None):
        if skip_tags is None:
            skip_tags = set()

        def walk(tokens):
            res = [tokens]
            todo = [tokens]

            while todo:
                for current_token in todo.pop():
                    children = current_token.children
                    if children:
                        todo.append(children)
                        if current_token.tagname not in skip_tags:
                            res.append(children)
            return res

        return walk


SECTION_TAG = "@section"


def get_recursive_tag_parser(tagname, blocknode=False):
    tag_parser = TagParser()
    tag_parser.add(tagname, 10, blocknode=blocknode)
    return tag_parser


parse_div = get_recursive_tag_parser("div", blocknode=True)


def parse_inputbox(tokens, xopts):
    get_recursive_tag_parser("inputbox")(tokens, xopts)

    for token in tokens:
        if token.tagname == "inputbox":
            token.inputbox = Token.join_as_text(token.children)
            del token.children[:]


def create(current, tokens, sections, index):
    if current.start is None or current.endtitle is None:
        return False
    start_equal_count = tokens[current.start].text.count("=")
    end_equal_count = tokens[current.endtitle].text.count("=")
    level = min(start_equal_count, end_equal_count)
    # KLUDGE: make this a caption
    caption = Token(
        type=Token.t_complex_node,
        children=tokens[current.start + 1 : current.endtitle],
    )
    if end_equal_count > start_equal_count and caption.children is not None:
        caption.children.append(
            Token(type=Token.t_text, text="=" * (end_equal_count - start_equal_count))
        )
    elif start_equal_count > end_equal_count and caption.children is not None:
        caption.children.insert(
            0,
            Token(type=Token.t_text, text="=" * (start_equal_count - end_equal_count)),
        )
    body = Token(
        type=Token.t_complex_node, children=tokens[current.endtitle + 1 : index]
    )
    sect = Token(
        type=Token.t_complex_section,
        tagname=SECTION_TAG,
        children=[caption, body],
        level=level,
        blocknode=True,
    )
    tokens[current.start : index] = [sect]
    while sections and level <= sections[-1].level:
        sections.pop()
    if sections:
        sections[-1].children.append(tokens[current.start])
        del tokens[current.start]
        current.start -= 1
    sections.append(sect)
    return True


def _something(tokens, sections, index, current):
    token = tokens[index]
    if token.type == Token.t_section:
        if create(current, tokens, sections, index) and current.start is not None:
            index = current.start + 1
            current = Bunch(start=None, end=None, endtitle=None)
        else:
            current.start = index
            index += 1
    elif token.type == Token.t_section_end:
        current.endtitle = index
        index += 1
    else:
        index += 1

    return index, current


def _parse_gallery_txt(txt, xopts):
    lines = [line.strip() for line in txt.split("\n")]
    sub = []
    for line in lines:
        if not line:
            continue
        if xopts.expander is None:
            raise ValueError("no expander in _parse_gallery_txt")
        xnew = xopts.expander.parseAndExpand(line, keep_uniq=True)

        linode = parse_txt("[[" + xnew + "]]", xopts)

        if linode:
            node = linode[0]
            if node.ns == nshandling.NS_IMAGE:
                sub.append(node)
                continue
        sub.append(Token(type=Token.t_text, text=xnew))
    return sub


class Bunch:
    start: int | None = None
    endtitle: int | None = None

    def __init__(self, **kw):
        self.__dict__.update(kw)


class ParseSections:
    def __init__(self, tokens, _):
        self.tokens = tokens
        self.run()

    def run(self):
        tokens = self.tokens
        index = 0

        sections = []
        current = Bunch(start=None, end=None, endtitle=None)

        while index < len(self.tokens):
            index, current = _something(tokens, sections, index, current)

        create(current, tokens, sections, len(tokens))


class ParseUrls:
    def __init__(self, tokens, xopts):
        self.tokens = tokens
        self.run()

    def run(self):
        tokens = self.tokens
        i = 0
        start = None
        while i < len(tokens):
            token = tokens[i]

            if token.type == Token.t_urllink and start is None:
                start = i
                i += 1
            elif (
                token.type == Token.t_special
                and token.text == "]"
                and start is not None
            ):
                sub = self.tokens[start + 1 : i]
                self.tokens[start : i + 1] = [
                    Token(
                        type=Token.t_complex_named_url,
                        children=sub,
                        caption=self.tokens[start].text[1:],
                    )
                ]
                i = start
                start = None
            elif token.type == Token.t_2box_close and start is not None:
                self.tokens[i].type = Token.t_special
                self.tokens[i].text = "]"
                sub = self.tokens[start + 1 : i]
                self.tokens[start:i] = [
                    Token(
                        type=Token.t_complex_named_url,
                        children=sub,
                        caption=self.tokens[start].text[1:],
                    )
                ]
                i = start
                start = None
            else:
                i += 1


class ParseSingleQuote:
    def __init__(self, tokens, xopts):
        self.tokens = tokens
        self.styles = []
        self.counts = []
        self.run()

    def finish(self):
        if len(self.counts) != len(self.styles):
            raise ValueError("len(self.counts) != len(self.styles)")

        states = styleanalyzer.compute_path(self.counts)

        last_apocount = 0
        for i, state in enumerate(states):
            apos = "'" * (state.apocount - last_apocount)
            if apos:
                self.styles[i].children.insert(0, Token(type=Token.t_text, text=apos))
            last_apocount = state.apocount

            if state.is_bold and state.is_italic:
                self.styles[i].caption = "'''"
                inner = Token(
                    type=Token.t_complex_style,
                    caption="''",
                    children=self.styles[i].children,
                )
                self.styles[i].children = [inner]
            elif state.is_bold:
                self.styles[i].caption = "'''"
            elif state.is_italic:
                self.styles[i].caption = "''"
            else:
                self.styles[i].type = Token.t_complex_node

    def _update_token_counts_and_styles(self, token, pos, start, tokens):
        if start is None:
            self.counts.append(len(token.text))
            start = pos
            pos += 1
        else:
            tokens[start:pos] = [
                Token(type=Token.t_complex_style, children=tokens[start + 1 : pos])
            ]
            self.styles.append(tokens[start])
            pos = start + 1
            start = None
        return pos, start

    def run(self):
        tokens = self.tokens
        pos = 0
        start = None
        self.counts = []
        self.styles = []

        while pos < len(tokens):
            token = tokens[pos]
            if token.type == Token.t_singlequote:
                pos, start = self._update_token_counts_and_styles(
                    token, pos, start, tokens
                )
            elif token.type == Token.t_newline:
                if start is not None:
                    tokens[start:pos] = [
                        Token(
                            type=Token.t_complex_style, children=tokens[start + 1 : pos]
                        )
                    ]
                    self.styles.append(tokens[start])
                    pos = start
                    start = None
                pos += 1

                if self.counts:
                    self.finish()
                    self.counts = []
                    self.styles = []
            else:
                pos += 1

        if start is not None:
            tokens[start:pos] = [
                Token(type=Token.t_complex_style, children=tokens[start + 1 : pos])
            ]
            self.styles.append(tokens[start])

        if self.counts:
            self.finish()


class ParsePreformatted:
    need_walker = False

    def __init__(self, tokens, xopts):
        walker = get_token_walker(skip_tags={"table", "li", "tr", SECTION_TAG})
        for token in walker(tokens):
            self.tokens = token
            self.run()

    def _handle_complex_preformatted_tokens(self, tokens, i, start):
        sub = tokens[start + 1 : i + 1]
        if start > 0 and tokens[start - 1].type == Token.t_complex_preformatted:
            del tokens[start : i + 1]
            tokens[start - 1].children.extend(sub)
            i = start
        else:
            tokens[start : i + 1] = [
                Token(
                    type=Token.t_complex_preformatted,
                    children=sub,
                    blocknode=True,
                )
            ]
            i = start + 1
        start = None
        return i, start

    def run(self):
        tokens = self.tokens
        i = 0
        start = None
        while i < len(tokens):
            token = tokens[i]
            if token.type == Token.t_pre:
                if token.type != Token.t_pre:
                    raise ValueError("t.type != Token.t_pre")
                start = i
                i += 1
            elif token.type == Token.t_newline and start is not None:
                i, start = self._handle_complex_preformatted_tokens(tokens, i, start)
            elif token.blocknode or (
                token.type == Token.t_complex_tag
                and token.tagname in ("blockquote", "table", "timeline", "div")
            ):
                start = None
                i += 1
            else:
                i += 1


class ParseLines:
    def __init__(self, tokens, xopts):
        self.tokens = tokens
        self.run()

    def splitdl(self, item):
        for i, child in enumerate(item.children):
            if child.type == Token.t_special and child.text == ":":
                token = Token(
                    type=Token.t_complex_style,
                    caption=":",
                    children=item.children[i + 1 :],
                )
                del item.children[i:]
                return token

    def analyze(self, lines):
        lines.append(Token(type=Token.t_complex_line, lineprefix="<guard>"))  # guard

        startpos = 0
        while startpos < len(lines) - 1:
            prefix = self.getchar(lines[startpos])
            if prefix is None:
                self.handle_no_prefix(lines, startpos)
                startpos += 1
                continue

            node, newitem, endtag = self.get_node_and_newitem(prefix)
            node.children = []
            description_data = None

            while startpos < len(lines) - 1 and self.getchar(lines[startpos]) == prefix:
                description_data, startpos, broke_loop = self.collect_items(
                    lines, startpos, prefix, node, newitem, endtag, description_data
                )
                if broke_loop:
                    break

            if isinstance(node, Token):
                node = Token(
                    type=node.type,
                    tagname=node.tagname,
                    caption=node.caption,
                    children=node.children,
                    blocknode=node.blocknode,
                )
            lines.insert(startpos, node)
            startpos += 1
            if description_data is not None:
                lines.insert(startpos, description_data)
                startpos += 1
        del lines[-1]  # remove guard

    def getchar(self, node):
        if node.type != Token.t_complex_line:
            raise ValueError("node.type != Token.t_complex_line")
        if node.lineprefix:
            return node.lineprefix[0]
        return None

    def handle_no_prefix(self, lines, startpos):
        if lines[startpos].tagname:
            lines[startpos].type = Token.t_complex_tag
        else:
            lines[startpos].type = Token.t_complex_node

    def get_node_and_newitem(self, prefix):
        if prefix == ":":
            node = Token(type=Token.t_complex_style, caption=":")

            def newitem() -> Token | None:
                return Token(type=Token.t_complex_node, blocknode=True)

            endtag = None
        elif prefix == "*":
            node = Token(type=Token.t_complex_tag, tagname="ul")

            def newitem() -> Token | None:
                return Token(type=Token.t_complex_tag, tagname="li", blocknode=True)

            endtag = "ul"
        elif prefix == "#":
            node = Token(type=Token.t_complex_tag, tagname="ol")

            def newitem() -> Token | None:
                return Token(type=Token.t_complex_tag, tagname="li", blocknode=True)

            endtag = "ol"
        elif prefix == ";":
            node = Token(type=Token.t_complex_style, caption=";")

            def newitem() -> Token | None:
                return Token(type=Token.t_complex_node, blocknode=True)

            endtag = None
        else:
            node = None

            def newitem() -> Token | None:
                return None

            endtag = None

        return node, newitem, endtag

    @staticmethod
    def append_line(lines, startpos, item, endtag=None):
        line = lines[startpos]
        if endtag:
            for i, child in enumerate(line.children):
                if child.rawtagname == endtag and child.type == Token.t_html_tag_end:
                    after = line.children[i + 1 :]
                    del line.children[i:]
                    item.children.append(line)
                    lines[startpos] = Token(
                        type=Token.t_complex_line,
                        tagname="p",
                        lineprefix=None,
                        children=after,
                    )
                    return

        item.children.append(lines[startpos])
        del lines[startpos]

    def collect_items(
        self, lines, startpos, prefix, node, newitem, endtag, description_data
    ):
        broke_loop = False
        while startpos < len(lines) - 1 and self.getchar(lines[startpos]) == prefix:
            item = newitem()
            item.children = []
            self.append_line(lines, startpos, item, endtag)

            while (
                startpos < len(lines) - 1
                and prefix == self.getchar(lines[startpos])
                and len(lines[startpos].lineprefix) > 1
            ):
                self.append_line(lines, startpos, item, endtag)

            for child in item.children:
                child.lineprefix = child.lineprefix[1:]
            self.analyze(item.children)
            node.children.append(item)
            if (
                prefix == ";"
                and item.children
                and item.children[0].type == Token.t_complex_node
            ):
                description_data = self.splitdl(item.children[0])
                if description_data is not None:
                    broke_loop = True
                    break
            if prefix in ":;":
                broke_loop = True
                break

        return description_data, startpos, broke_loop

    def get_line_prefix(self, start_line):
        return (self.tokens[start_line].text or "").strip()

    def run(self):
        i = 0
        lines = []
        start_line = None
        first_token = None

        while i is not None and i < len(self.tokens):
            token = self.tokens[i]
            if token.type in (Token.t_item, Token.t_colon):
                i, start_line, first_token = self.process_item_and_colon(i, first_token)
            elif token.type == Token.t_newline and start_line is not None:
                i, start_line = self.process_newline_when_start_line_exists(
                    i, start_line, lines
                )
            elif token.type == Token.t_break:
                i, start_line, first_token, lines = self.process_break(
                    i, start_line, first_token, lines
                )
            else:
                if start_line is None and lines:
                    self.analyze(lines)
                    self.tokens[first_token:i] = lines
                    i = first_token
                    lines = []
                    first_token = None
                else:
                    i += 1

        if start_line is not None:
            sub = self.tokens[start_line + 1 :]
            lines.append(
                Token(
                    type=Token.t_complex_line,
                    start=self.tokens[start_line].start,
                    children=sub,
                    lineprefix=self.get_line_prefix(start_line),
                )
            )

        if lines:
            self.analyze(lines)
            self.tokens[first_token:] = lines

    def process_break(self, i, start_line, first_token, lines):
        if start_line is not None:
            sub = self.tokens[start_line + 1 : i]
            lines.append(
                Token(
                    type=Token.t_complex_line,
                    start=self.tokens[start_line].start,
                    len=0,
                    children=sub,
                    lineprefix=self.get_line_prefix(start_line),
                )
            )
            start_line = None
        if lines:
            self.analyze(lines)
            self.tokens[first_token:i] = lines
            i = first_token
            first_token = None
            lines = []
            return i, start_line, first_token, lines
        first_token = None
        lines = []
        i += 1
        return i, start_line, first_token, lines

    def process_newline_when_start_line_exists(self, i, start_line, lines):
        sub = self.tokens[start_line + 1 : i + 1]
        lines.append(
            Token(
                type=Token.t_complex_line,
                start=self.tokens[start_line].start,
                len=0,
                children=sub,
                lineprefix=self.get_line_prefix(start_line),
            )
        )
        start_line = None
        i += 1
        return i, start_line

    @staticmethod
    def process_item_and_colon(i, first_token):
        if first_token is None:
            first_token = i
        start_line = i
        i += 1
        return i, start_line, first_token


class ParseLinks:
    def __init__(self, tokens, xopts):
        self.xopts = xopts
        lang = xopts.lang
        imagemod = xopts.imagemod

        self.tokens = tokens
        self.lang = lang

        self.nshandler = xopts.nshandler
        if self.nshandler is None:
            raise ValueError("nshandler not set")

        if imagemod is None:
            imagemod = util.ImageMod()
        self.imagemod = imagemod

        self.run()

    def handle_image_modifier(self, mod, node):
        mod_type, mod_match = self.imagemod.parse(mod)
        if mod_type is None:
            return False
        util.handle_imagemod(node, mod_type, mod_match)
        if node.thumb or node.align or node.frame == "frame":
            node.blocknode = True

        return True

    def extract_image_modifiers(self, marks, node):
        cap = None
        for i in range(1, len(marks) - 1):
            tmp = self.tokens[marks[i] + 1 : marks[i + 1]]
            if not self.handle_image_modifier(Token.join_as_text(tmp), node):
                cap = tmp
        return cap

    def run(self):
        tokens = self.tokens
        i = 0
        marks = []

        stack = []

        while i < len(self.tokens):
            token = tokens[i]
            if token.type == Token.t_2box_open:
                i, marks = self.process_2box_open(i, marks, stack)
            elif token.type == Token.t_newline and len(marks) < 2:
                i, marks = self.process_newline(i, stack)
            elif token.type == Token.t_special and token.text == "|":
                i = self.process_special(i, marks)
            elif token.type == Token.t_2box_close and marks:
                i, marks = self.process_2box_close(i, marks, stack, tokens)
            else:
                i += 1

    def process_2box_close(self, i, marks, stack, tokens):
        marks.append(i)
        start = marks[0]
        colon, target = self.process_colon_and_target(marks, start, tokens)
        ilink = self.nshandler.resolve_interwiki(target)
        if ilink:
            url = ilink.url
            ns_handling = None
            partial = ilink.partial
            langlink = ilink.language
            interwiki = ilink.prefix
            full = None
        else:
            url, ns_handling, partial, target, full = self.process_non_ilink_target(
                target
            )
            langlink = None
            interwiki = None
        if not ilink and not partial:
            i += 1
            marks = stack.pop() if stack else []
            return i, marks
        node = Token(
            type=Token.t_complex_link,
            children=[],
            ns=ns_handling,
            colon=colon,
            lang=self.lang,
            nshandler=self.nshandler,
            url=url,
        )
        if langlink:
            node.langlink = langlink
        if interwiki:
            node.interwiki = interwiki
        sub = self.process_sub(marks, node, ns_handling, tokens)
        node.children = sub
        tokens[start : i + 1] = [node]
        node.target = target
        node.full_target = full
        marks = stack.pop() if stack else []
        i = start + 1
        return i, marks

    def process_non_ilink_target(self, target):
        if target.startswith("/") and self.xopts.title:
            ns_handling, partial, full = self.nshandler.splitname(
                self.xopts.title + target
            )
            if full.endswith("/"):
                full = full[:-1]
                target = target[1:-1]
        else:
            ns_handling, partial, full = self.nshandler.splitname(target)
        url = self.xopts.wikidb.get_url(full) if self.xopts.wikidb is not None else None
        return url, ns_handling, partial, target, full

    def process_colon_and_target(self, marks, start, tokens):
        target = Token.join_as_text(tokens[start + 1 : marks[1]]).strip()
        target = target.strip("\u200e\u200f")
        if target.startswith(":"):
            target = target[1:]
            colon = True
        else:
            colon = False
        return colon, target

    def process_sub(self, marks, node, ns_handling, tokens):
        sub = None
        if ns_handling == nshandling.NS_IMAGE:
            sub = self.extract_image_modifiers(marks, node)
        elif len(marks) > 2:
            sub = tokens[marks[1] + 1 : marks[-1]]
        if sub is None:
            sub = []
        return sub

    def process_special(self, i, marks):
        marks.append(i)
        i += 1
        return i

    def process_newline(self, i, stack):
        marks = stack.pop() if stack else []
        i += 1
        return i, marks

    def process_2box_open(self, i, marks, stack):
        if len(marks) > 1:
            stack.append(marks)
        marks = [i]
        i += 1
        return i, marks


class ParseParagraphs:
    need_walker = False

    def __init__(self, tokens, xopts):
        walker = get_token_walker(
            skip_tags={"p", "ol", "ul", "table", "tr", SECTION_TAG}
        )
        for token in walker(tokens):
            self.tokens = token
            self.run()

    def run(self):
        tokens = self.tokens
        i = 0
        first = 0

        def create(delta=1):
            sub = tokens[first:i]
            if sub:
                tokens[first : i + delta] = [
                    Token(
                        type=Token.t_complex_tag,
                        tagname="p",
                        children=sub,
                        blocknode=True,
                    )
                ]

        while i < len(self.tokens):
            token = tokens[i]
            if token.type == Token.t_break:
                create()
                first += 1
                i = first
            elif token.blocknode:  # blocknode
                create(delta=0)
                first += 1
                i = first
            else:
                i += 1

        if first:
            create()


class CombinedParser:
    def __init__(self, parsers):
        self.parsers = parsers

    def __call__(self, tokens, xopts):
        parsers = list(self.parsers)

        default_walker = get_token_walker(skip_tags={"table", "tr", SECTION_TAG})

        while parsers:
            parser = parsers.pop()

            need_walker = getattr(parser, "need_walker", True)
            if need_walker:
                log.debug(f"using default token walker for {parser}")
                walker = default_walker
                for token in walker(tokens):
                    parser(token, xopts)
            else:
                parser(tokens, xopts)


def _create(tokens, i, start, state):
    if not state or i <= start:
        return False
    outer = None
    children = tokens[start:i]
    for tag, tok in state.items():
        outer = Token(
            type=Token.t_complex_tag, tagname=tag, children=children, vlist=tok.vlist
        )
        children = [outer]
    tokens[start:i] = [outer]
    return True


def mark_style_tags(tokens, xopts):  # pylint: disable=unused-argument
    tags = set(
        ["mapframe", "abbr", "tt", "strike", "ins", "del", "small", "sup", "sub", "b", "strong", "cite", "i", "u", "em", "big", "font", "s", "var", "kbd"]
    )

    todo = [(0, {}, tokens)]

    while todo:
        i, state, tokens = todo.pop()
        start = i
        while i < len(tokens):
            current_token = tokens[i]
            if (
                current_token.type == Token.t_html_tag
                and current_token.rawtagname in tags
            ):
                i, start, continue_loop = _process_html_tag(
                    current_token, i, start, state, tokens
                )
                if continue_loop:
                    continue
            elif (
                current_token.type == Token.t_html_tag_end
                and current_token.rawtagname in tags
            ):
                i, start = _process_html_tag_end(current_token, i, start, state, tokens)
            elif current_token.children:
                i, start = _process_current_token_children(
                    current_token, i, start, state, todo, tokens
                )
                break
            else:
                i += 1
        _create(tokens, i, start, state)


def _process_current_token_children(current_token, i, start, state, todo, tokens):
    if _create(tokens, i, start, state):
        start += 1
        i = start
    if tokens[i] is not current_token:
        raise ValueError("tokens[i] is not current_token")
    if current_token.type in (
        Token.t_complex_table,
        Token.t_complex_table_row,
        Token.t_complex_table_cell,
    ):
        todo.append((i + 1, state, tokens))
        todo.append((0, {}, current_token.children))
    else:
        todo.append((i + 1, state, tokens))
        todo.append((0, state, current_token.children))
    return i, start


def _process_html_tag_end(current_token, i, start, state, tokens):
    del tokens[i]
    raw_tag_name = current_token.rawtagname
    if raw_tag_name not in state:
        if raw_tag_name == "sup":
            raw_tag_name = "sub"
        elif raw_tag_name == "sub":
            raw_tag_name = "sup"
    if raw_tag_name in state:
        if _create(tokens, i, start, state):
            start += 1
            i = start
        del state[raw_tag_name]
    return i, start


def _process_html_tag(current_token, i, start, state, tokens):
    del tokens[i]
    continue_loop = False
    if current_token.tag_selfClosing:
        continue_loop = True
        return i, start, continue_loop
    if current_token.rawtagname in state:
        if _create(tokens, i, start, state):
            start += 1
            i = start
        start = i

        del state[current_token.rawtagname]
        continue_loop = True
        return i, start, continue_loop
    if _create(tokens, i, start, state):
        start += 1
        i = start
    start = i
    state[current_token.rawtagname] = current_token
    return i, start, continue_loop


mark_style_tags.need_walker = False


class ParseUniq:
    def __init__(self, tokens, xopts):
        self.tagextensions = tagext.default_registry

        uniquifier = xopts.uniquifier
        if uniquifier is None:
            return

        i = 0
        while i < len(tokens):
            current_token = tokens[i]
            if current_token.type != Token.t_uniq:
                i += 1
                continue

            text = current_token.text
            try:
                match = uniquifier.uniq2repl[text]
            except KeyError:
                i += 1
                continue

            vlist = match["vlist"]
            vlist = util.parse_params(vlist) if vlist else None

            inner = match["inner"]
            name = match["tagname"]

            try:
                method = getattr(self, "create_" + str(name))
            except AttributeError:
                method = self._create_generic

            tokens[i] = method(name, vlist, inner or "", xopts)
            if tokens[i] is None:
                del tokens[i]
            else:
                i += 1

    def _create_generic(self, name, vlist, inner, xopts):
        if not vlist:
            vlist = {}
        if name in self.tagextensions:
            node = self.tagextensions[name](inner, vlist)
            retval = (
                None
                if node is None
                else Token(type=Token.t_complex_compat, compatnode=node)
            )

            return retval

        children = [Token(type=Token.t_text, text=inner)]
        return Token(
            type=Token.t_complex_tag, tagname=name, vlist=vlist, children=children
        )

    def create_pre(self, name, vlist, inner, xopts):
        inner = util.replace_html_entities(util.remove_nowiki_tags(inner))
        return self._create_generic(name, vlist, inner, xopts)

    def create_source(self, name, vlist, inner, _xopts):
        children = [Token(type=Token.t_text, text=inner)]
        blocknode = True
        if vlist and vlist.get("enclose", "") == "none":
            blocknode = False

        return Token(
            type=Token.t_complex_tag,
            tagname=name,
            vlist=vlist,
            children=children,
            blocknode=blocknode,
        )

    def create_ref(self, _name, vlist, inner, xopts):
        expander = xopts.expander
        if expander is not None and inner:
            inner = expander.parseAndExpand(inner, True)

        if inner:
            # <ref>* not an item</ref>
            children = parse_txt("<br />" + inner, xopts)
            if children[0].children:  # paragraph had been created...
                del children[0].children[0]
            else:
                del children[0]
        else:
            children = []

        return Token(
            type=Token.t_complex_tag, tagname="ref", vlist=vlist, children=children
        )

    def create_timeline(self, _name, vlist, inner, _xopts):
        return Token(
            type=Token.t_complex_tag,
            tagname="timeline",
            vlist=vlist,
            timeline=inner,
            blocknode=True,
        )

    def create_math(self, _name, vlist, inner, _xopts):
        return Token(type=Token.t_complex_tag, tagname="math", vlist=vlist, math=inner)

    def create_gallery(self, _name, vlist, inner, xopts):
        sub = _parse_gallery_txt(inner, xopts)
        return Token(
            type=Token.t_complex_tag,
            tagname="gallery",
            vlist=vlist,
            children=sub,
            blocknode=True,
        )

    def create_poem(self, _name, vlist, inner, xopts):
        expander = xopts.expander
        if expander is not None and inner:
            inner = expander.parseAndExpand(inner, True)

        res = ["\n"]
        for line in inner.split("\n"):
            if line.strip():
                res.append(":")
            if line.startswith(" "):
                res.append("&nbsp;")
            res.append(line.strip())
            res.append("\n")
        res.append("\n")
        res = "".join(res)
        children = parse_txt(res, xopts)
        return Token(
            type=Token.t_complex_tag, tagname="poem", vlist=vlist, children=children
        )

    def create_imagemap(self, _, vlist, inner, xopts):
        txt = inner
        token = Token(type=Token.t_complex_tag, tagname="imagemap", vlist=vlist)
        token.imagemap = imgmap.image_map_from_string(txt)
        if token.imagemap.image:
            token.imagemap.imagelink = None
            image_syntax = "[[" + token.imagemap.image + "]]"
            res = parse_txt(image_syntax, xopts)
            if res and res[0].type == Token.t_complex_link and res[0].ns == 6:
                token.imagemap.imagelink = res[0]

        return token

    def create_nowiki(self, _, _vlist, inner, _xopts):
        txt = inner
        txt = util.replace_html_entities(txt)
        return Token(type=Token.t_text, text=txt)

    def create_pages(self, name, vlist, _, xopts):
        expander = xopts.expander

        if not vlist:
            vlist = {}
        start_page = vlist.get("from")
        end_page = vlist.get("to")
        children = []
        if start_page and end_page and expander:
            nshandler = expander.nshandler
            page_ns = nshandler._find_namespace("Page")[1]

            try:
                start_index = int(start_page)
                end_index = int(end_page)
            except ValueError:
                start_page = nshandler.get_fqname(start_page, page_ns)
                end_page = nshandler.get_fqname(end_page, page_ns)
                pages = expander.db.select(start_page, end_page)
            else:
                base = vlist.get("index", "")
                base = nshandler.get_fqname(base, page_ns)
                pages = [f"{base}/{i}" for i in range(start_index, end_index + 1)]

            rawtext = "".join("{{%s}}\n" % x for x in pages)
            template_expander = expander.__class__(
                rawtext, pagename=expander.pagename, wikidb=expander.db
            )
            children = parse_txt(
                template_expander.expandTemplates(True),
                xopts=XBunch(**xopts.__dict__),
                expander=template_expander,
                uniquifier=template_expander.uniquifier,
            )

        return Token(
            type=Token.t_complex_tag, tagname=name, vlist=vlist, children=children
        )


class XBunch:
    expander: Any | None = None
    imagemod: Any | None = None
    nshandler: Any | None = None
    uniquifier: Any | None = None

    def __init__(self, **kw):
        self.__dict__.update(kw)

    def __getattr__(self, name):
        return None


def fix_urllink_inside_link(tokens, _xopt):
    idx = 0
    last = None
    while idx < len(tokens) - 1:
        token = tokens[idx]
        if token.type == Token.t_2box_open:
            last = Token.t_2box_open
        elif token.type == Token.t_urllink:
            last = Token.t_urllink
        elif (
            token.type == Token.t_2box_close
            and tokens[idx + 1].type == Token.t_special
            and tokens[idx + 1].text == "]"
            and last == Token.t_urllink
        ):
            tokens[idx], tokens[idx + 1] = tokens[idx + 1], tokens[idx]

        idx += 1


def fix_named_url_double_brackets(tokens, xopt):
    idx = 0
    while idx < len(tokens) - 1:
        token = tokens[idx]
        if token.type == Token.t_2box_open and tokens[idx + 1].type == Token.t_http_url:
            tokens[idx].text = "["
            tokens[idx].type = Token.t_special
            tokens[idx + 1].text = "[" + tokens[idx + 1].text
            tokens[idx + 1].type = Token.t_urllink
        idx += 1
    fix_urllink_inside_link(tokens, xopt)


def fix_break_between_pre(tokens, xopt):
    idx = 0
    while idx < len(tokens) - 1:
        token = tokens[idx]
        if (
            token.type == Token.t_break
            and token.text.startswith(" ")
            and tokens[idx + 1].type == Token.t_pre
        ):
            tokens[idx : idx + 1] = [
                Token(type=Token.t_pre, text=" "),
                Token(type=Token.t_newline, text="\n"),
            ]
            idx += 2
        else:
            idx += 1


def fix_li_tags(tokens, xopts):
    root = Token(type=Token.t_complex_tag, tagname="div")
    todo = [(root, tokens)]
    while todo:
        parent, tokens = todo.pop()
        if parent.tagname not in ("ol", "ul"):
            process_li_tokens(tokens)

        for token in tokens:
            if token.children:
                todo.append((token, token.children))


def process_li_tokens(tokens):
    idx = 0
    while idx < len(tokens):
        start = idx
        while idx < len(tokens) and tokens[idx].tagname == "li":
            idx += 1

        if idx > start:
            lst = Token(
                type=Token.t_complex_tag, tagname="ul", children=tokens[start:idx]
            )
            tokens[start : idx + 1] = [lst]
            idx = start + 1
        else:
            idx += 1


fix_li_tags.need_walker = False


def parse_txt(txt, xopts=None, **kwargs):
    if xopts is None:
        xopts = XBunch(**kwargs)
    else:
        xopts.__dict__.update(**kwargs)

    if xopts.expander is None:
        from mwlib.parser.expander import DictDB, Expander

        xopts.expander = Expander("", "pagename", wikidb=DictDB())

    if xopts.nshandler is None:
        xopts.nshandler = nshandling.get_nshandler_for_lang(xopts.lang or "en")

    xopts.imagemod = util.ImageMod(xopts.magicwords)

    uniquifier = xopts.uniquifier
    if uniquifier is None:
        log.debug(f"creating uniquifier for {txt}")
        uniquifier = uniq.Uniquifier()
        txt = uniquifier.replace_tags(txt)
        xopts.uniquifier = uniquifier

    if not txt:
        return []
    tokens = tokenize(txt, uniquifier=uniquifier)

    td2 = TagParser()
    add_tag_2 = td2.add

    add_tag_2("code", 10)
    add_tag_2("span", 20)

    add_tag_2("li", 25, blocknode=True, nested=False)
    add_tag_2("dl", 28, blocknode=True)
    add_tag_2("dt", 26, blocknode=True, nested=False)
    add_tag_2("dd", 26, blocknode=True, nested=True)

    td1 = TagParser()
    add_tag_1 = td1.add
    add_tag_1("blockquote", 5)
    add_tag_1("references", 15)

    add_tag_1("p", 30, blocknode=True, nested=False)
    add_tag_1("ul", 35, blocknode=True)
    add_tag_1("ol", 40, blocknode=True)
    add_tag_1("center", 45, blocknode=True)

    td_parse_h = TagParser()
    for i in range(1, 7):
        td_parse_h.add("h%s" % i, i)

    parsers = [
        fix_li_tags,
        mark_style_tags,
        ParseSingleQuote,
        ParsePreformatted,
        td2,
        ParseParagraphs,
        td1,
        ParseLines,
        parse_div,
        ParseLinks,
        ParseUrls,
        parse_inputbox,
        td_parse_h,
        ParseSections,
        TableGarbageRemover,
        TableFixer,
        TableParser,
        ParseUniq,
        fix_named_url_double_brackets,
        fix_break_between_pre,
    ]

    CombinedParser(parsers)(tokens, xopts)
    return tokens
