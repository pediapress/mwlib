# -*- compile-command: "../../tests/test_refine.py" -*-

# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

from mwlib.parser.refine import util
from mwlib.parser.token.utoken import Token as T


class TableCellParser:
    def __init__(self, tokens, _):
        self.tokens = tokens
        self.run()

    def is_table_cell_start(self, token):
        return token.type == T.t_column or (
            token.type == T.t_html_tag and token.rawtagname in ("td", "th")
        )

    def is_table_cell_end(self, token):
        return token.type == T.t_html_tag_end and token.rawtagname in ("td", "th")

    def find_modifier(self, cell):
        children = cell.children
        if not children:
            return
        for index, _ in enumerate(children):
            token = children[index]
            if token.type == T.t_2box_open:
                break
            if token.type == T.t_special and token.text == "|":
                mod = T.join_as_text(children[:index])
                cell.vlist = util.parse_params(mod)

                del children[: index + 1]
                return

    def replace_tablecaption(self, children):
        index = 0
        while index < len(children):
            if children[index].type == T.t_tablecaption:
                children[index].type = T.t_special
                children[index].text = "|"
                children.insert(index + 1, T(type=T.t_text, text="+"))
            index += 1

    def make_cell(self, tokens, start, index, skip_end=0):
        token = tokens[start].text.strip()
        if token == "|":
            self.is_header = False
        elif token == "!":
            self.is_header = True
        is_header = self.is_header
        if tokens[start].rawtagname == "th":
            is_header = True
        elif tokens[start].rawtagname == "td":
            is_header = False
        tagname = "th" if is_header else "td"
        search_modifier = tokens[start].text.strip() in ("|", "!", "||", "!!")
        sub = tokens[start + 1: index - skip_end]
        self.replace_tablecaption(sub)
        tokens[start:index] = [
            T(
                type=T.t_complex_table_cell,
                tagname=tagname,
                start=tokens[start].start,
                children=sub,
                vlist=tokens[start].vlist,
                is_header=is_header,
            )
        ]
        if search_modifier:
            self.find_modifier(tokens[start])

    def run(self):
        tokens = self.tokens
        index = 0
        start = None
        self.is_header = False

        while index < len(tokens):
            if self.is_table_cell_start(tokens[index]):
                if start is not None:
                    self.make_cell(tokens, start, index)
                    start += 1
                    index = start + 1
                else:
                    start = index
                    index += 1

            elif self.is_table_cell_end(tokens[index]):
                if start is not None:
                    index += 1
                    self.make_cell(tokens, start, index, skip_end=1)
                    index = start + 1
                    start = None
                else:
                    index += 1
            else:
                index += 1

        if start is not None:
            self.make_cell(tokens, start, index)


class TableRowParser:
    def __init__(self, tokens, xopts):
        self.tokens = tokens
        self.xopts = xopts
        self.run()

    def is_table_row_start(self, token):
        return token.type == T.t_row or (
            token.type == T.t_html_tag and token.rawtagname == "tr"
        )

    def is_table_row_end(self, token):
        return token.type == T.t_html_tag_end and token.rawtagname == "tr"

    def find_modifier(self, row):
        children = row.children
        for i, child in enumerate(children):
            if child.type in (T.t_newline, T.t_break):
                mod = T.join_as_text(children[:i])
                row.vlist = util.parse_params(mod)
                del children[:i]
                return

    def is_table_cell_start(self, token):
        return token.type == T.t_column or (
            token.type == T.t_html_tag and token.rawtagname in ("td", "th")
        )

    def should_find_modifier(self, row_begin_token):
        return not(row_begin_token is None or row_begin_token.rawtagname)

    def args(self, row_begin_token):
        if row_begin_token is None:
            return {}
        return {"vlist": row_begin_token.vlist}

    def _handle_table_row_tokens(self, start, i, tokens, row_begin_token, remove_start):
        if start is not None:
            children = tokens[start + remove_start: i]
            tokens[start:i] = [
                T(
                    type=T.t_complex_table_row,
                    tagname="tr",
                    start=tokens[start].start,
                    children=children,
                    **self.args(row_begin_token)
                )
            ]
            if self.should_find_modifier(row_begin_token):
                self.find_modifier(tokens[start])
            TableCellParser(children, self.xopts)
            start += 1  # we didn't remove the start symbol above
            row_begin_token = tokens[start]
            remove_start = 1
            i = start + 1
        else:
            row_begin_token = tokens[i]
            remove_start = 1
            start = i
            i += 1
        return start, i, row_begin_token, remove_start

    def extract_complex_table_row(self, tokens, start, i, row_begin_token, remove_start):
        sub = tokens[start + remove_start: i]
        tokens[start: i + 1] = [
            T(
                type=T.t_complex_table_row,
                tagname="tr",
                start=tokens[start].start,
                children=sub,
                **self.args(row_begin_token)
            )
        ]
        if self.should_find_modifier(row_begin_token):
            self.find_modifier(tokens[start])
        TableCellParser(sub, self.xopts)

    def run(self):
        tokens = self.tokens
        i = 0

        start = None
        remove_start = 1
        row_begin_token = None

        while i < len(tokens):
            if start is None and self.is_table_cell_start(tokens[i]):
                row_begin_token = None
                start = i
                remove_start = 0
                i += 1
            elif self.is_table_row_start(tokens[i]):
                start, i, row_begin_token, remove_start = self._handle_table_row_tokens(start, i, tokens, row_begin_token, remove_start)
            elif self.is_table_row_end(tokens[i]):
                if start is not None:
                    self.extract_complex_table_row(tokens, start, i, row_begin_token, remove_start)
                    i = start + 1
                    start = None
                    row_begin_token = None
                else:
                    i += 1
            else:
                i += 1

        if start is not None:
            sub = tokens[start + remove_start:]
            tokens[start:] = [
                T(
                    type=T.t_complex_table_row,
                    tagname="tr",
                    start=tokens[start].start,
                    children=sub,
                    **self.args(row_begin_token)
                )
            ]
            if self.should_find_modifier(row_begin_token):
                self.find_modifier(tokens[start])
            TableCellParser(sub, self.xopts)


class TableParser:
    def __init__(self, tokens, xopts):
        self.xopts = xopts
        self.tokens = tokens
        self.run()

    def is_table_start(self, token):
        return token.type == T.t_begin_table or (
            token.type == T.t_html_tag and token.rawtagname == "table"
        )

    def is_table_end(self, token):
        return token.type == T.t_end_table or (
            token.type == T.t_html_tag_end and token.rawtagname == "table"
        )

    def handle_rows(self, sublist):
        TableRowParser(sublist, self.xopts)

    def find_modifier(self, table):
        children = table.children

        def compute_mod():
            mod = T.join_as_text(children[:i])
            table.vlist = util.parse_params(mod)
            del children[:i]

        i = 0
        for i, child in enumerate(children):
            if child.type in (T.t_newline, T.t_break):
                break

        compute_mod()

    def parse_complex_caption(self, children, start, i, modifier):
        if modifier:
            mod = T.join_as_text(children[start:modifier])
            vlist = util.parse_params(mod)
            sub = children[modifier + 1: i]
        else:
            sub = children[start + 1: i]
            vlist = {}

        caption = T(type=T.t_complex_caption, children=sub, vlist=vlist)
        children[start:i] = [caption]

    def find_caption(self, table):
        children = table.children
        start = None
        i = 0
        while i < len(children):
            token = children[i]
            if token.type == T.t_tablecaption:
                start = i
                i += 1
                break

            if token.text is None or token.text.strip():
                return
            i += 1

        modifier = None

        while i < len(children):
            token = children[i]
            if token.tagname not in ("ref",) and (
                token.text is None or token.text.startswith("\n")
            ):
                self.parse_complex_caption(children, start, i, modifier)
                return
            elif token.text == "|" and modifier is None:
                modifier = i
            elif token.type == T.t_2box_open and modifier is None:
                modifier = 0

            i += 1

    def run(self):
        tokens = self.tokens
        index = 0
        stack = []

        def make_table():
            start = stack.pop()
            starttoken = tokens[start]
            sub = tokens[start + 1:index]
            from mwlib.parser.refine import core

            tag_parser = core.TagParser()
            tag_parser.add("caption", 5)
            tag_parser(sub, self.xopts)
            tokens[start:index + 1] = [
                T(
                    type=T.t_complex_table,
                    tagname="table",
                    start=tokens[start].start,
                    children=sub,
                    vlist=starttoken.vlist,
                    blocknode=True,
                )
            ]
            if starttoken.text.strip() == "{|":
                self.find_modifier(tokens[start])
            self.handle_rows(sub)
            self.find_caption(tokens[start])
            return start

        while index < len(tokens):
            if self.is_table_start(tokens[index]):
                stack.append(index)
                index += 1
            elif self.is_table_end(tokens[index]):
                if stack:
                    index = make_table() + 1
                else:
                    index += 1
            else:
                index += 1

        while stack:
            make_table()


class TableFixer:
    def __init__(self, tokens, xopts):
        self.xopts = xopts
        self.tokens = tokens
        self.run()

    def run(self):
        tokens = self.tokens
        for token in tokens:
            if token.type != T.t_complex_table:
                continue

            rows = [
                child
                for child in token.children
                if child.type in (T.t_complex_table_row, T.t_complex_caption)
            ]
            if not rows:
                token.type = T.t_complex_node
                token.tagname = None


def find_end_of_garbage(tokens, start, index, res, is_allowed):
    while index < len(tokens):
        if is_allowed(tokens[index]):
            break
        index += 1

    garbage = tokens[start:index]
    del tokens[start:index]
    index = start
    res.append(T(type=T.t_complex_node, children=garbage))
    return index


def extract_garbage(tokens, is_allowed, is_whitespace=None):
    if is_whitespace is None:

        def is_whitespace(token):
            return token.type in (T.t_newline, T.t_break)

    res = []
    index = 0
    start = None

    while index < len(tokens):
        if is_whitespace(tokens[index]):
            if start is None:
                start = index
            index += 1
        elif is_allowed(tokens[index]):
            start = None
            index += 1
        else:
            if start is None:
                start = index
            index += 1
            # find end of garbage
            index = find_end_of_garbage(tokens, start, index, res, is_allowed)

    return res


class TableGarbageRemover:
    need_walker = False

    def __init__(self, tokens, xopts):
        from mwlib.parser.refine import core

        walker = core.get_token_walker()
        for token in walker(tokens):
            self.tokens = token
            self.run()

    def run(self):
        tokens = self.tokens
        tableidx = 0
        while tableidx < len(tokens):
            if tokens[tableidx].type == T.t_complex_table:
                tmp = []
                for child in tokens[tableidx].children:
                    if child.type == T.t_complex_table_row:
                        rowgarbage = extract_garbage(
                            child.children,
                            is_allowed=lambda token: token.type in (T.t_complex_table_cell,),
                        )
                        tmp.extend(rowgarbage)

                tokens[tableidx + 1: tableidx + 1] = tmp
            tableidx += 1
