#! /usr/bin/env py.test

from mwlib import dummydb, parser, expander, uparser
from mwlib.expander import DictDB

parse = uparser.simpleparse


def test_simple_table():
    r = parse("""{|
|-
| A || B
|-
| C || D
|}""")
    table = r.find(parser.Table)[0]
    print "TABLE:", table

    assert len(table.children) == 2, "expected two rows"
    for x in table.children:
        assert len(x.children) == 2, "expected 2 cells"


def test_parse_caption():
    s = """{|
|+ caption
|}
"""
    n = parse(s)
    t = n.find(parser.Table)[0]
    assert isinstance(t.children[0], parser.Caption), "expected a caption node"


def test_table_header():
    s = """
{|
|-
! header1 !! header2
|-
| cell1 || cell2
|}
"""

    r = parse(s)
    cells = r.find(parser.Cell)
    assert len(cells) == 4


def test_table_header_2():
    s = """
{|
|-
! header 1 || header 2
| header 3
|-
| cell 1 || cell 2
! cell 3
|}
"""
    r = parse(s)
    cells = r.find(parser.Cell)
    is_header = [x.is_header for x in cells]
    assert is_header == [True, True, False, False, False, True]


def test_caption_modifier():
    s = """
{|
|+style="font-size: 1.25em;" | caption
|-
| cell1
| cell2
|}
"""
    r = parse(s)
    c = r.find(parser.Caption)[0]
    assert c.vlist


def _get_styled_txt(s):
    r = parse(s)
    styles = r.find(parser.Style)
    txt = " ".join(x.asText() for x in styles)
    return txt


def test_table_vs_style_tags_cell_barrier():
    s = """
{|
|-
| cell1<b>bold
| cell2<b>
|}
after
"""
    txt = _get_styled_txt(s)

    assert "cell2" not in txt
    assert "after" not in txt


def test_table_vs_style_tags_continue_after():
    s = """
<b>
{|
|-
| cell1
| cell2
|}
after
"""

    txt = _get_styled_txt(s)
    assert "cell1" not in txt
    assert "after" in txt
