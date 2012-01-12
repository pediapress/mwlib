#! /usr/bin/env py.test

from mwlib.refine import core
from mwlib import nshandling
from mwlib.xfail import xfail

tokenize = core.tokenize
show = core.show
T = core.T


def parse_txt(*args, **kwargs):
    p = core.parse_txt(*args, **kwargs)
    core.show(p)
    return p


def empty():
    empty = core.XBunch()
    empty.nshandler = nshandling.get_nshandler_for_lang('de')
    return empty


def test_parse_row_missing_beginrow():
    tokens = tokenize("<td>implicit row starts here</td><td>cell2</td>")
    core.parse_table_rows(tokens, empty())
    show(tokens)
    assert len(tokens) == 1
    assert tokens[0].type == T.t_complex_table_row
    assert [x.type for x in tokens[0].children] == [T.t_complex_table_cell] * 2


def test_parse_table_cells_missing_close():
    tokens = core.tokenize("<td>bla")
    core.parse_table_cells(tokens, empty())
    show(tokens)
    assert tokens[0].type == T.t_complex_table_cell, "expected a complex table cell"


def test_parse_table_cells_closed_by_next_cell():
    tokens = core.tokenize("<td>foo<td>bar")
    core.parse_table_cells(tokens, empty())
    show(tokens)
    assert tokens[0].type == T.t_complex_table_cell
    assert tokens[1].type == T.t_complex_table_cell

    assert len(tokens[0].children) == 1
    assert tokens[0].children[0]


def test_parse_table_cells_pipe():
    tokens = tokenize("{|\n|cell0||cell1||cell2\n|}")[2:-2]
    print "BEFORE:"
    show(tokens)
    core.parse_table_cells(tokens, empty())
    print "AFTER"
    show(tokens)
    assert len(tokens) == 3

    for i, x in enumerate(tokens):
        print "cell", i
        assert x.type == T.t_complex_table_cell, "cell %s bad" % (i,)
        assert len(x.children) == 1, "cell %s has wrong number of children" % (i,)
        assert x.children[0].type == T.t_text
        assert x.children[0].text == ('cell%s' % i)


def test_parse_cell_modifier():
    tokens = tokenize("""{|
|align="right"|cell0|still_cell0
|}""")[2:-2]

    print "BEFORE:"
    show(tokens)
    core.parse_table_cells(tokens, empty())
    print "AFTER"
    show(tokens)
    assert tokens[0].type == T.t_complex_table_cell
    assert tokens[0].vlist == dict(align="right")
    assert T.join_as_text(tokens[0].children) == "cell0|still_cell0"


def test_parse_table_modifier():
    tokens = tokenize("""{| border="1"
|}
""")

    print "BEFORE:"
    show(tokens)
    core.parse_tables(tokens, empty())

    print "AFTER:"
    show(tokens)

    assert tokens[0].type == T.t_complex_table
    assert tokens[0].vlist == dict(border=1)


def test_parse_table_row_modifier():
    tokens = tokenize("""{|
|- style="background:red; color:white"
| cell
|}
""")[2:-2]

    print "BEFORE:"
    show(tokens)
    core.parse_table_rows(tokens, empty())

    print "AFTER:"
    show(tokens)

    assert tokens[0].vlist


def test_parse_link():
    tokens = tokenize("[[link0]][[link2]]")
    core.parse_links(tokens, empty())
    show(tokens)
    assert len(tokens) == 2
    assert tokens[0].type == T.t_complex_link
    assert tokens[1].type == T.t_complex_link


def test_no_row_modifier():
    s = "{|\n|foo||bar\n|}"
    r = core.parse_txt(s)
    core.show(r)
    cells = list(core.walknode(r, lambda x: x.type == core.T.t_complex_table_cell))
    print "CELLS:", cells
    assert len(cells) == 2, "expected 2 cells"


def test_parse_para_vs_preformatted():
    s = ' foo\n\nbar\n'
    r = core.parse_txt(s)
    core.show(r)
    pre = list(core.walknode(r, lambda x: x.type == core.T.t_complex_preformatted))[0]
    core.show(pre)
    textnodes = list(core.walknode(pre, lambda x: x.type == core.T.t_text))
    txt = ''.join([x.text for x in textnodes])
    assert u'bar' not in txt


def test_duplicate_nesting():
    s = u"""<b>
[[foo|bar]] between
</b>"""
    r = core.parse_txt(s)
    bolds = list(core.walknode(r, lambda x: x.tagname == "b"))
    core.show(bolds)

    for x in bolds:
        for y in x.children or []:
            assert y.tagname != "b"


def test_ref_no_newline():
    s = u"""<ref>* no item</ref>"""
    r = core.parse_txt(s)
    core.show(r)
    linodes = list(core.walknode(r, lambda x: x.tagname == "li"))
    assert not linodes


def test_tab_table():
    s = """
\t{|
|-
\t| cell1
| cell2
\t|}after
"""
    r = core.parse_txt(s)
    core.show(r)
    tables = []

    def allowed(node):
        retval = bool(tables)
        if node.type == T.t_complex_table:
            tables.append(node)
        return retval
    nodes = [x for x in r if allowed(x)]
    assert nodes, "bad  or no table"

    cells = core.walknodel(r, lambda x: x.type == T.t_complex_table_cell)
    assert len(cells) == 2, "expected two cells"


def test_parse_ul_not_preformatted():
    """http://code.pediapress.com/wiki/ticket/554"""
    s = """
<ul>
   <li>bla blub
   <li>bla bla
 </ul>
"""
    r = parse_txt(s)
    core.show(r)
    pre = core.walknodel(r, lambda x: x.type == T.t_complex_preformatted)
    assert not pre, "should contain no preformatted nodes"


def test_link_vs_center():
    """http://code.pediapress.com/wiki/ticket/559"""
    s = """[[foo|bar <center> not closed]]"""
    r = parse_txt(s)
    core.show(r)
    assert r[0].type == T.t_complex_link, "expected a link"


def test_no_combine_dd_dt():
    """http://code.pediapress.com/wiki/ticket/549"""
    def doit(s):
        r = parse_txt(s)
        core.show(r)
        styles = core.walknodel(r, lambda x: x.type == T.t_complex_style)
        print styles
        assert len(styles) == 2

    yield doit, ":first\n:second\n"
    yield doit, ";first\n;second\n"


def test_combine_preformatted():
    """http://code.pediapress.com/wiki/ticket/569"""
    s = " preformatted\n and more preformatted\n"
    r = parse_txt(s)
    core.show(r)
    pre = core.walknodel(r, lambda x: x.type == T.t_complex_preformatted)
    assert len(pre) == 1, "expected exactly one preformatted node"


def test_bad_section():
    """http://code.pediapress.com/wiki/ticket/588"""
    s = """<div>
div ends here
== this is </div> a section title ==
some text
"""
    r = parse_txt(s)
    show(r)


def test_mark_style_595():
    """http://code.pediapress.com/wiki/ticket/595"""
    r = parse_txt('<b><i>[[Article link|Display text]]</i></b> after')
    b = core.walknodel(r, lambda x: x.tagname == "b")
    print b
    assert len(b) == 1, "expected exactly one bold node"


def test_unexpected_end():
    """http://code.pediapress.com/wiki/ticket/607"""
    parse_txt("{|")


def test_link_in_table_caption():
    """http://code.pediapress.com/wiki/ticket/578"""
    s = """{|
|+ id="CFNP" [[bla | blubb]]
|-
| a || b
|}
"""
    r = parse_txt(s)
    with_vlist = core.walknodel(r, lambda x: bool(x.vlist))
    print with_vlist

    assert not with_vlist,  "no node should contain a vlist"


def test_html_entity_in_pre():
    r = parse_txt("<pre>&gt;</pre>")
    txt = r[0].children[0].text
    print txt
    assert txt == ">",  "wrong text"


def test_nowiki_in_pre():
    """http://code.pediapress.com/wiki/ticket/617"""
    r = parse_txt("<pre><nowiki>foo</nowiki></pre>")
    txt = r[0].children[0].text
    print txt
    assert txt == "foo",  "wrong text"


def test_s_tag():
    r = parse_txt("<s>strike</s>")
    s = core.walknodel(r, lambda x: x.tagname == "s")
    assert len(s) == 1


def test_var_tag():
    r = parse_txt("<var>strike</var>")
    s = core.walknodel(r, lambda x: x.tagname == "var")
    assert len(s) == 1


def test_empty_link():
    """http://code.pediapress.com/wiki/ticket/621"""
    r = parse_txt("[[de:]]")
    print r
    assert r[0].type == T.t_complex_link


def test_source():
    r = parse_txt("foo <source>bar</source> baz")
    show(r)
    assert r[0].tagname == "p"
    assert r[1].tagname == "source"
    assert r[1].blocknode == True
    assert r[2].tagname == "p"


def test_source_enclose():
    r = parse_txt('foo <source enclose="none">bar</source> baz')
    show(r)
    assert r[0].type == T.t_text
    assert r[1].tagname == "source"
    assert r[1].blocknode == False
    assert r[2].type == T.t_text


def test_urllink_in_link():
    """http://code.pediapress.com/wiki/ticket/602"""
    r = parse_txt("[[foo|[http://baz.com baz]]]")
    li = core.walknodel(r, lambda x: x.type == T.t_complex_link)
    assert len(li) == 1,  "expected one link"
    nu = core.walknodel(r, lambda x: x.type == T.t_complex_named_url)
    show(r)
    assert len(nu) == 1, "expected exactly one named url"


def test_urllink_in_brackets():
    """http://code.pediapress.com/wiki/ticket/556"""
    r = parse_txt("[[http://example.com bla]]")
    show(r)
    nu = core.walknodel(r, lambda x: x.type == T.t_complex_named_url)
    print nu
    assert len(nu) == 1,  "expected exactly one named url"


def test_lines_with_table_space():
    parse_txt("""* foo
 :{|
 |-
 | bar
 | baz
 |}
""")


def test_sub_close_sup():
    """http://code.pediapress.com/wiki/ticket/634"""
    r = parse_txt("<sup>foo</sub>bar")
    show(r)
    assert "bar" not in T.join_as_text(r[0].children), "bar should not be inside sup tag"


def test_sup_close_sub():
    """http://code.pediapress.com/wiki/ticket/634"""
    r = parse_txt("<sub>foo</sup>bar")
    show(r)
    assert "bar" not in T.join_as_text(r[0].children), "bar should not be inside sub tag"


def test_dd_dt_tags_inside_table():
    r = parse_txt("""{|
|-
| blubb <dl> bla <dt>foobazbar</dt>
|}
<dl> bla <dt>foobazbar</dt>
""")
    show(r)
    #assert 0 # FIXME


def test_left_to_right_mark():
    def doit(s):
        r = parse_txt(s)
        show(r)
        target = r[0].target
        assert target == "Image:foo.jpg", "wrong target"

    for mark in (u"\u200e", u"\u200f"):
        s = u"[[Image:foo.jpg" + mark + "|thumb|foobar]]"
        yield doit, s


def test_image_blocknode():

    def blocknode(s):
        r = parse_txt(s)[0]
        assert r.blocknode

    def noblocknode(s):
        r = parse_txt(s)[0]
        assert not r.blocknode

    yield noblocknode, "[[Image:foo.png]]"
    yield noblocknode, "[[Image:foo.png|150px]]"
    yield noblocknode, "[[Image:foo.png|frameless]]"

    yield blocknode, "[[Image:foo.png|left]]"
    yield blocknode, "[[Image:foo.png|thumb]]"
    yield blocknode, "[[Image:foo.png|frame]]"


def test_no_preformatted_inside_li():
    """stupid: http://code.pediapress.com/wiki/ticket/676"""
    r = parse_txt("""<ol><li>in li:
  foo
  bar
</li></ol>
""")
    core.show(r)
    pre = core.walknodel(r, lambda x: x.type == T.t_complex_preformatted)
    assert not pre,  "should not contain preformatted"


def test_preformatted_empty_line():
    r = parse_txt("foo\n  pre1\n  \n  pre2\nbar\n")
    core.show(r)
    pre = core.walknodel(r, lambda x: x.type == T.t_complex_preformatted)
    assert len(pre) == 1, "expected exactly one preformatted node"


def test_inputbox():
    s = "</inputbox>"

    r = core.parse_txt(s)
    core.show(r)


def test_ref_inside_caption():
    s = """
{|
|+ table capshun <ref>references fun</ref>
| hey || ho
|}"""
    r = core.parse_txt(s)
    core.show(r)
    cap = core.walknodel(r, lambda x: x.type == T.t_complex_caption)[0]
    print "caption:"
    core.show(cap)
    refs = core.walknodel(cap, lambda x: x.tagname == "ref")
    assert refs


def test_tr_inside_caption():
    """http://code.pediapress.com/wiki/ticket/709"""
    s = """
{|
|+ table capshun <tr><td>bla</td></tr>
|}"""
    r = core.parse_txt(s)
    core.show(r)
    cap = core.walknodel(r, lambda x: x.type == T.t_complex_caption)[0]
    print "caption:"
    core.show(cap)

    rows = core.walknodel(r, lambda x: x.type == T.t_complex_table_row)
    print "ROWS:",  rows
    assert len(rows) == 1,  "no rows found"

    rows = core.walknodel(cap, lambda x: x.type == T.t_complex_table_row)
    print "ROWS:",  rows
    assert len(rows) == 0, "row in table caption found"


def test_ul_inside_star():
    """http://code.pediapress.com/wiki/ticket/735"""
    r = core.parse_txt("""
* foo
* bar </ul> baz
""")
    core.show(r)
    ul = core.walknodel(r, lambda x: x.tagname == "ul")

    def baz(x):
        if x.text and "baz" in x.text:
            return True

    b1 = core.walknodel(ul, baz)
    b2 = core.walknodel(r, baz)

    assert not b1, "baz should not be inside ul"
    assert b2,  "baz missing"


def test_div_vs_link():
    r = core.parse_txt("""[[File:ACDC_logo.gif|thumb| <div style="background-color:#fee8ab"> foo ]]""")
    core.show(r)
    assert r[0].type == T.t_complex_link,  "expected an image link"


def test_link_vs_section():
    r = core.parse_txt("[[acdc\n== foo ]] ==\n")
    core.show(r)
    assert r[0].type != T.t_complex_link, "should not parse a link here"


def test_div_vs_section():
    r = core.parse_txt("""== foo <div style="background-color:#ff0000"> bar ==
baz
""")
    core.show(r)
    assert r[0].level == 2,  "expected a section"


def test_comment_in_gallery():
    """http://code.pediapress.com/wiki/ticket/741"""
    r = core.parse_txt("""<gallery>
Image:ACDC_logo.gif|capshun<!--comment-->
</gallery>
""")
    core.show(r)
    txt = T.join_as_text(core.walknodel(r[0].children,  lambda x: True))
    print "TXT:",  repr(txt)
    assert "capshun" in txt, "bad text??"
    assert "comment" not in txt,  "comment not stripped"


def test_parserfun_in_gallery():
    r = core.parse_txt("""<gallery>
Image:ACDC_logo.gif| capshun {{#if: 1|yes}}

</gallery>
""")
    core.show(r)
    txt = T.join_as_text(core.walknodel(r[0].children,  lambda x: True))
    print "TXT:",  repr(txt)
    assert "capshun" in txt, "bad text??"
    assert "capshun yes" in txt,  "#if failed to expand"


def test_span_vs_lines():
    r = core.parse_txt("""* foo <span> bar
* baz
""")
    core.show(r)

    ul = core.walknodel(r, lambda x: x.tagname == "ul")
    assert len(ul) == 1,  "expected one list"


def test_named_url_in_double_brackets():
    """http://code.pediapress.com/wiki/ticket/556"""
    r = core.parse_txt("[[http://foo.com baz]]")
    core.show(r)
    named = core.walknodel(r, lambda x: x.type == T.t_complex_named_url)
    assert len(named) == 1, "expected a named url"
    txt = T.join_as_text(r)
    print "TXT:",  repr(txt)
    assert "[" in txt, "missing ["
    assert "]" in txt, "missing ]"
    assert "[[" not in txt, "bad text"
    assert "]]" not in txt, "bad text"


def test_link_vs_namedurl():
    r = core.parse_txt("[[acdc [http://web.de bla]]")
    core.show(r)
    txt = T.join_as_text(r)
    print "TXT:",  repr(txt)

    assert "[[acdc " in txt, "wrong text"
    assert txt.endswith("]"), "wrong text"

    assert r[0].type != T.t_complex_link, "should not be an article link"

    urls = core.walknodel(r, lambda x: x.type == T.t_complex_named_url)
    assert len(urls) == 1, "no named url found"


def test_span_vs_paragraph():
    """http://code.pediapress.com/wiki/ticket/751"""
    r = core.parse_txt("foo<span>\n\nbar</span>\n\n")
    core.show(r)
    p = [x for x in r if x.tagname == "p"]
    print "PARAS:",  p
    assert len(p) == 2,  "expected two paragraphs"

    txts = [T.join_as_text(x.children) for x in p]
    print txts
    assert "foo" in txts[0]
    assert "bar" in txts[1]


def test_last_unitialized():
    """last variable was not initialized in fix_urllink_inside_link"""
    core.parse_txt("]]]")


def test_style_tag_closes_same():
    r = core.parse_txt("foo<u>bar<u>baz")
    core.show(r)
    utags = core.walknodel(r, lambda x: x.tagname == "u")

    print "utags:", utags
    txt = "".join([T.join_as_text(x.children) for x in utags])
    print "txt:", txt
    assert txt == u"bar"


def test_hashmark_link():
    r = core.parse_txt("[[#foo]]")
    core.show(r)
    assert r[0].type == T.t_complex_link, "not a link"


def test_ref_drop_text_newlines():
    """http://code.pediapress.com/wiki/ticket/812"""
    r = core.parse_txt("<ref>bar\n\n</ref>")
    core.show(r)
    txt = T.join_as_text(core.walknodel(r, lambda x: 1))
    assert "bar" in txt, "text dropped"


def test_sections_same_depth():
    s = """=Level 1=
foo
==Level 2A==
bar
==Level 2B==
baz"""
    r = parse_txt(s)
    assert len(r) == 1, "section not nested"


def test_references_with_paragraphs():
    s = "<references>\n\n<ref>bla</ref>\n\n</references>"
    r = core.parse_txt(s)
    core.show(r)
    references = core.walknodel(r, lambda x: x.tagname == "references")
    assert len(references) == 1, "expected exactly one references node, got %s" % len(references)
    refs = core.walknodel(references, lambda x: x.tagname == "ref")
    assert len(refs) == 1, "expected exactly one ref node inside the references node, got %s" % len(refs)


def test_newline_in_link_target():
    """http://code.pediapress.com/wiki/ticket/906"""
    s = "[[Albert\nEinstein]]"
    r = core.parse_txt(s)
    core.show(r)
    links = core.walknodel(r, lambda x: x.type == T.t_complex_link)
    assert not links, "links found"


def test_newline_in_link_text():
    """http://code.pediapress.com/wiki/ticket/906"""
    s = "[[Albert Einstein | Albert\nEinstein]]"
    r = core.parse_txt(s)
    core.show(r)
    links = core.walknodel(r, lambda x: x.type == T.t_complex_link)
    assert links, "no links found"
