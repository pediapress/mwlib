#! /usr/bin/env py.test

# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

import pytest

from mwlib import parser
from mwlib.parser import expander
from mwlib.parser.dummydb import DummyDB
from mwlib.parser.expander import DictDB
from mwlib.parser.refine import uparser, util
from mwlib.parser.templ.misc import expand_str
from mwlib.parser.token.utoken import show

BAD_URL = "bad url"
BAD_VLIST = "bad vlist"
EXPECTED_EXACTLY_ONE_CELL = "expected exactly one cell"
EXPECTED_A_LINK = "expected a link"
EXPECTED_A_NAMED_LINK = "expected a NamedLink"
EXPECTED_A_PREFORMATTED_NODE = "expected a preformatted node"
WRONG_NAMESPACE = "wrong namespace"
WRONG_TARGET = "wrong target"

parse = uparser.simpleparse


def test_headings():
    r = parse(
        """
= 1 =
== 2 ==
= 3 =
"""
    )

    sections = [
        x.children[0].as_text().strip() for x in r.children if isinstance(x, parser.Section)
    ]
    assert sections == ["1", "3"]


def check_style(s, counts):
    print("PARSING:", repr(s))
    art = parse(s)
    styles = art.find(parser.Style)
    assert len(styles) == len(counts), "wrong number of styles"
    for i, x in enumerate(styles):
        assert len(x.caption) == counts[i]


def test_style():
    check_style("''frankfurt''", (2,))
    check_style("'''mainz'''", (3,))
    check_style("'''''hamburg'''''", (3, 2))
    check_style("'''''foo'' bla'''", (3, 2, 3))
    check_style("'''''mainz''' bla''", (3, 2, 2))
    check_style("'''''''''''''''''''pp'''''", (3, 2))
    check_style("'''test''bla", (2,))


def test_style_fails():
    """http://code.pediapress.com/wiki/ticket/375"""

    check_style("'''strong only ''also emphasized'' strong only'''", (3, 3, 2, 3))


def test_single_quote_after_style():
    """http://code.pediapress.com/wiki/ticket/20"""

    def check(s, outer, inner=None):
        art = parse(s)
        styles = art.find(parser.Style)
        style = styles[0]
        assert style.caption == outer
        if inner is None:
            assert len(styles) == 1
        else:
            assert len(styles) == 2
            assert styles[1].caption == inner

    check("''pp'''s", "''")
    check("'''pp''''s", "'''")
    check("''pp'''", "''")
    check("'''pp''''", "'''")
    check("'''''pp''''''", "'''", "''")
    check("'''''''''''''''''''pp''''''", "'''", "''")


def test_links_in_style():
    s = parse("'''[[mainz]]'''").find(parser.Style)[0]
    assert isinstance(s.children[0], parser.Link)


def test_parse_image_inline():
    r = parse(
        '{| cellspacing="2" border="0" cellpadding="3" bgcolor="#EFEFFF" width="100%"\n|-\n| width="12%" bgcolor="#EEEEEE"| 9. Juli 2006\n| width="13%" bgcolor="#EEEEEE"| Berlin\n| width="20%" bgcolor="#EEEEEE"| [[Bild:flag of Italy.svg|30px]] \'\'\'Italien\'\'\'\n| width="3%" bgcolor="#EEEEEE"| \u2013\n| width="20%" bgcolor="#EEEEEE"| [[Bild:flag of France.svg|30px]] Frankreich\n| width="3%" bgcolor="#EEEEEE"|\n| width="25%" bgcolor="#EEEEEE"| [[Fu\xdfball-Weltmeisterschaft 2006/Finalrunde#Finale: Italien .E2.80.93 Frankreich 6:4 n. E..2C 1:1 n. V. .281:1.2C 1:1.29|6:4 n. E., (1:1, 1:1, 1:1)]]\n|}\n',
        lang="de",
    )
    images = r.find(parser.ImageLink)

    assert len(images) == 2

    for i in images:
        assert i.is_inline() is True
        print("-->Image:", i, i.is_inline())


def test_parse_image_6():
    """http://code.pediapress.com/wiki/ticket/6"""
    r = parse("[[Bild:img.jpg|thumb|+some text]] [[Bild:img.jpg|thumb|some text]]", lang="de")

    images = r.find(parser.ImageLink)
    assert len(images) == 2
    print(images)
    assert images[0].is_inline() == images[1].is_inline()


def test_self_closing_nowiki():
    parse("<nowiki/>")
    parse("<nowiki  />")
    parse("<nowiki       />")
    parse("<NOWIKI>[. . .]</NOWIKI>")


def test_switch_default():
    db = DictDB(
        Bonn="""{{Infobox
|Bundesland         = Nordrhein-Westfalen
}}
""",
        Infobox="""{{#switch: {{{Bundesland}}}
        | Bremen = [[Bremen (Land)|Bremen]]
        | #default = [[{{{Bundesland|Bayern}}}]]
}}
""",
    )

    te = expander.Expander(
        db.normalize_and_get_page("Bonn", 0).rawtext, pagename="thispage", wikidb=db
    )
    res = te.expandTemplates()

    print("EXPANDED:", repr(res))
    assert "Nordrhein-Westfalen" in res


def test_tag_expand_vs_uniq():
    db = DictDB(Foo="""{{#tag:pre|inside pre}}""")
    r = uparser.parse_string(title="Foo", wikidb=db)
    show(r)
    pre = r.find(parser.PreFormatted)
    assert len(pre) == 1, EXPECTED_A_PREFORMATTED_NODE


def test_pipe_table():
    db = DictDB(
        Foo="""
bla
{{{ {{Pipe}}}
blubb
""",
        Pipe="|",
    )

    te = expander.Expander(
        db.normalize_and_get_page("Foo", 0).rawtext, pagename="thispage", wikidb=db
    )
    res = te.expandTemplates()

    print("EXPANDED:", repr(res))
    assert "bla" in res
    assert "blubb" in res


def test_pipe_begin_table():
    db = DictDB(
        Foo="""
bla
{{{Pipe}} |}
blubb
""",
        Pipe="|",
    )

    te = expander.Expander(
        db.normalize_and_get_page("Foo", 0).rawtext, pagename="thispage", wikidb=db
    )
    res = te.expandTemplates()

    print("EXPANDED:", repr(res))
    assert "bla" in res
    assert "blubb" in res
    assert "{|" in res


def test_cell_parse_bug():
    """http://code.pediapress.com/wiki/ticket/17"""
    # mediawiki actually pulls out that ImageLink from the table...

    r = parse(
        """{|
|-
[[Image:bla.png|bla]]
|}"""
    )
    print(r)

    images = r.find(parser.ImageLink)
    assert images


def test_table_not_eating():
    """internal parser error.
    http://code.pediapress.com/wiki/ticket/32
    http://code.pediapress.com/wiki/ticket/29"""
    uparser.simpleparse(
        """{|)
|10<sup>10<sup>100</sup></sup>||gsdfgsdfg
|}"""
    )


def test_table_not_eating2():
    """internal parser error.
    http://code.pediapress.com/wiki/ticket/32
    http://code.pediapress.com/wiki/ticket/29"""
    uparser.simpleparse(
        """{|
<tr><td>'''Birth&nbsp;name'''</td><td colspan="2">Alanis Nadine Morissette</td></tr><tr><td>'''Born'''</td>
|}
"""
    )


def test_parse_comment():
    ex = """foo
<!-- comment --->
bar"""
    expanded = expand_str(ex)
    print("EXPANDED:", expanded)
    assert "\n\n" not in expanded


def test_nowiki_entities():
    """http://code.pediapress.com/wiki/ticket/40"""
    node = parse("<nowiki>&amp;</nowiki>")
    txt = node.find(parser.Text)[0]
    assert txt.caption == "&", "expected an ampersand"


def test_blockquote_with_newline():
    """http://code.pediapress.com/wiki/ticket/41"""
    node = parse("<blockquote>\nblockquoted</blockquote>").find(parser.Style)[0]
    print("STYLE:", node)
    assert "blockquoted" in node.as_text(), "expected 'blockquoted'"


def test_blockquote_with_two_paras():
    """http://code.pediapress.com/wiki/ticket/41"""

    node = parse("<blockquote>\nblockquoted\n\nmust be inside</blockquote>")
    print("BLOCKQUOTE:", node.children)
    assert len(node.children) == 1, "expected exactly one child node"


def test_newlines_in_bold_tag():
    """http://code.pediapress.com/wiki/ticket/41"""
    node = parse("<b>test\n\nfoo</b>")
    styles = node.find(parser.Style)
    txt = "".join([x.as_text() for x in styles])
    print("TXT:", txt)

    assert "foo" in txt, "foo should be bold"


def test_percent_table_style():
    """http://code.pediapress.com/wiki/ticket/39. thanks xyb."""

    def check(s):
        r = parse(s)
        t = r.find(parser.Table)[0]
        print(t)
        assert t.vlist["width"] == "80%", "got wrong value {!r}".format(t.vlist["width"])

    check(
        """{| class="toccolours" width="80%"
|-
| foo
|}"""
    )

    check(
        """{| class="toccolours" width=80%
|-
| foo
|}"""
    )


def test_parse_params():
    def check(s, expected):
        res = util.parse_params(s)
        print(repr(s), "-->", res, "expected:", expected)

        assert res == expected, "bad result"

    check("width=80pt", {"width": "80pt"})
    check("width=80ex", {"width": "80ex"})


def test_ol_ul():
    """http://code.pediapress.com/wiki/ticket/33"""

    r = parse("#num\n*bul\n")
    lists = r.find(parser.ItemList)
    assert len(lists) == 2, "expected two ItemList children"

    r = parse("*num\n#bul\n")
    lists = r.find(parser.ItemList)
    assert len(lists) == 2, "expected two ItemList children"


def test_nested_lists():
    """http://code.pediapress.com/wiki/ticket/33"""
    r = parse(
        """
# lvl 1
#* lvl 2
#* lvl 2
# lvl 1
"""
    )
    lists = r.find(parser.ItemList)
    assert len(lists) == 2, "expected two lists"

    outer = lists[0]
    inner = lists[1]
    assert len(outer.children) == 2, "outer list must have 2 children"
    assert len(inner.children) == 2, "inner list must have 2 children"


def test_nested_list_listitem():
    r = parse("** wurst\n")
    outer = r.find(parser.ItemList)[0]
    assert isinstance(outer.children[0], parser.Item), "expected an Item inside ItemList"


def checktag(tagname):
    source = f"<{tagname}>foobar</{tagname}>"
    r = parse(source)
    print("R:", r)
    nodes = r.find(parser.TagNode)
    print("NODES:", nodes)
    assert len(nodes) == 1, "expected a TagNode"
    n = nodes[0]
    assert n.caption == tagname, "expected another node"


def test_strike_tag():
    checktag("strike")


def test_del_tag():
    checktag("del")


def test_ins_tag():
    checktag("ins")


def test_tt_tag():
    checktag("tt")


def test_code_tag():
    checktag("code")


def test_center_tag():
    checktag("center")


def test_headings_nonclosed():
    r = parse("= nohead\nbla")
    print("R:", r)
    sections = r.find(parser.Section)
    assert sections == [], "expected no sections"


def test_headings_unbalanced_1():
    r = parse("==head=")  # section caption should '=head'
    print("R:", r)
    section = r.find(parser.Section)[0]
    print("SECTION:", section)
    print("as_text:", section.as_text())

    assert section.level == 1, "expected level 1 section"
    assert section.as_text() == "=head"


def test_headings_unbalanced_2():
    r = parse("=head==")  # section caption should 'head='
    print("R:", r)
    section = r.find(parser.Section)[0]
    print("SECTION:", section)
    print("as_text:", section.as_text())

    assert section.level == 1, "expected level 1 section"
    assert section.as_text() == "head="


def test_headings_tab_end():
    r = parse("=heading=\t")
    print("R:", r)
    assert isinstance(r.children[0], parser.Section), "expected first child to be a Section"


def test_table_extra_cells_and_rows():
    """http://code.pediapress.com/wiki/ticket/19"""
    s = """
<table>
  <tr>
    <td>1</td>
  </tr>
</table>"""
    r = parse(s)
    cells = r.find(parser.Cell)
    assert len(cells) == 1, EXPECTED_EXACTLY_ONE_CELL

    rows = r.find(parser.Row)
    assert len(rows) == 1, "expected exactly one row"


def test_table_rowspan():
    """http://code.pediapress.com/wiki/ticket/19"""
    s = """
<table align="left">
  <tr align="right">
    <td rowspan=3 colspan=18>1</td>
  </tr>
</table>"""
    r = parse(s)
    cells = r.find(parser.Cell)
    assert len(cells) == 1, EXPECTED_EXACTLY_ONE_CELL
    cell = cells[0]
    print("VLIST:", cell.vlist)
    assert cell.vlist == {"rowspan": 3, "colspan": 18}, "bad vlist in cell"

    row = r.find(parser.Row)[0]
    print("ROW:", row)
    assert row.vlist == {"align": "right"}, "bad vlist in row"

    table = r.find(parser.Table)[0]
    print("TABLE.VLIST:", table.vlist)
    assert table.vlist == {"align": "left"}, "bad vlist in table"


def test_extra_cell_stray_tag():
    """http://code.pediapress.com/wiki/ticket/18"""
    cells = parse(
        """
{|
| bla bla </sub> dfg sdfg
|}"""
    ).find(parser.Cell)
    assert len(cells) == 1, EXPECTED_EXACTLY_ONE_CELL


def test_gallery_complex():
    gall = """<gallery caption="Sample gallery" widths="100px" heights="100px" perrow="6">
Image:Drenthe-Position.png|[[w:Drenthe|Drenthe]], the least crowded province
Image:Flevoland-Position.png
Image:Friesland-Position.png|[[w:Friesland|Friesland]] has many lakes
Image:Gelderland-Position.png
Image:Groningen-Position.png
Image:Limburg-Position.png
Image:Noord_Brabant-Position.png
Image:Noord_Holland-Position.png
Image:Overijssel-Position.png
Image:Zuid_Holland-Position.png|[[w:South Holland|South Holland]], the most crowded province
lakes
Image:Zeeland-Position.png
</gallery>
"""
    res = parse(gall).find(parser.TagNode)[0]
    print("VLIST:", res.vlist)
    print("RES:", res)

    assert res.vlist == {
        "caption": "Sample gallery",
        "heights": "100px",
        "perrow": 6,
        "widths": "100px",
    }
    assert len(res.children) == 12, "expected 12 children"
    assert isinstance(res.children[10], parser.Text), "expected text for the 'lakes' line"


def test_colon_nobr():
    tagnodes = parse(";foo\n:bar\n").find(parser.TagNode)
    assert not tagnodes, "should have no br tagnodes"


def test_nonascii_in_tags():
    r = parse("<dfg\u0147>")
    assert r.children[0].source == "<dfg\u0147>", "Non-ASCII in tag doesn't work"


def test_mailto_named():
    r = parse("[mailto:ralf@brainbot.com me]")
    assert r.find(parser.NamedURL), EXPECTED_A_NAMED_LINK


def test_irc_named():
    r = parse("[irc://freenode.net/pediapress #pediapress]")
    assert r.find(parser.NamedURL), EXPECTED_A_NAMED_LINK


def test_irc():
    r = parse("irc://freenode.net/pediapress #pediapress")
    assert r.find(parser.URL), "expected a URL"


def test_news_named():
    r = parse("[news:alt.foo.bar #pediapress]")
    assert r.find(parser.NamedURL), EXPECTED_A_NAMED_LINK


def test_news():
    r = parse("news:alt.foo.bar #pediapress")
    assert r.find(parser.URL), "expected a URL"


def test_namedurl_inside_link():
    r = parse("[http://foo.com baz]]]")
    assert r.find(parser.NamedURL), "expected a NamedURL"


def test_namedurl_with_style():
    """http://code.pediapress.com/wiki/ticket/461"""
    r = parse("[http://thetangent.org Internetpräsenz von ''The Tangent'']")
    named = r.find(parser.NamedURL)
    assert len(named) == 1, "expected a NamedURL instance"
    styles = named[0].find(parser.Style)
    assert len(styles) == 1, "expected a style"


def test_mailto():
    r = parse("mailto:ralf@brainbot.com")
    assert r.find(parser.URL), "expected a URL node"


def _check_text_in_pretag(txt):
    r = parse("<pre>%s</pre>" % txt)
    p = r.find(parser.PreFormatted)[0]
    assert len(p.children) == 1, "expected exactly one child node inside PreFormatted"
    t = p.children[0]
    assert t == parser.Text(txt), "child node contains wrong text"


def test_pre_tag_newlines():
    """http://code.pediapress.com/wiki/ticket/79"""
    _check_text_in_pretag("\ntext1\ntext2\n\ntext3")


def test_pre_tag_list():
    """http://code.pediapress.com/wiki/ticket/82"""
    _check_text_in_pretag("\n* item1\n* item2")


def test_pre_tag_link():
    """http://code.pediapress.com/wiki/ticket/78"""
    _check_text_in_pretag("\ntext [[link]] text\n")


def test_parse_preformatted_pipe():
    """http://code.pediapress.com/wiki/ticket/92"""
    r = parse(" |foobar\n")
    assert r.find(parser.PreFormatted), EXPECTED_A_PREFORMATTED_NODE


def test_parse_preformatted_math():
    r = parse(" <math>1+2=3</math>\n")
    assert r.find(parser.PreFormatted), EXPECTED_A_PREFORMATTED_NODE


def test_parse_preformatted_blockquote():
    r = parse(" <blockquote>blub</blockquote>")
    stylenode = r.find(parser.Style)
    assert (
        not r.find(parser.PreFormatted) and stylenode and stylenode[0].caption == "-"
    ), "expected blockquote w/o preformatted node"


def test_no_preformatted_with_source():
    """http://code.pediapress.com/wiki/ticket/174"""

    s = """  <source>

  </source>
* foo
"""
    r = parse(s)
    p = r.find(parser.PreFormatted)
    print(p)
    assert not p, "should not contain a preformatted node"


def test_parse_eolstyle_inside_blockquote():
    r = parse("<blockquote>\n:foo</blockquote>")
    stylenode = r.find(parser.Style)[-1]
    assert stylenode.caption == ":", "bad stylenode"


def _parse_url(u):
    url = parse("url: %s " % u).find(parser.URL)[0]
    assert url.caption == u, "url has wrong caption"


def test_url_parsing_plus():
    _parse_url("http://mw/foo+bar")


def test_url_parsing_comma():
    _parse_url("http://mw/foo,bar")


def test_url_parsing_umlauts():
    "http://code.pediapress.com/wiki/ticket/77"

    _parse_url("http://aÄfoo.de")
    _parse_url("http://aäfoo.de")

    _parse_url("http://aüfoo.de")
    _parse_url("http://aÜfoo.de")

    _parse_url("http://aöfoo.de")
    _parse_url("http://aÖfoo.de")


def test_table_markup_in_link_pipe_plus():
    """http://code.pediapress.com/wiki/ticket/54"""
    r = parse("[[bla|+blubb]]").find(parser.Link)[0]
    assert r.target == "bla", WRONG_TARGET


def test_table_markup_in_link_pipe_pipe():
    """http://code.pediapress.com/wiki/ticket/54"""
    r = parse("[[bla||blubb]]").find(parser.Link)[0]
    assert r.target == "bla", WRONG_TARGET


def test_table_markup_in_link_table_pipe_plus():
    """http://code.pediapress.com/wiki/ticket/11"""
    r = parse("{|\n|+\n|[[bla|+blubb]]\n|}").find(parser.Link)[0]
    assert r.target == "bla", WRONG_TARGET


def test_table_markup_in_link_table_pipe_pipe():
    """http://code.pediapress.com/wiki/ticket/11"""

    r = parse("{|\n|+\n|[[bla||blubb]]\n|}").find(parser.Link)
    assert not r, "table should not contain a link"


#     r=parse("{|\n|+\n|[[bla||blubb]]\n|}").find(parser.Link)[0]
#     assert r.target=='bla', WRONG_TARGET


def test_source_tag():
    source = "\nwhile(1){ {{#expr:1+1}}\n  i++;\n}\n\nreturn 0;\n"
    s = '<source lang="c">%s</source>' % source

    r = parse(s).find(parser.TagNode)[0]
    print(r)
    assert r.vlist["lang"] == "c", "wrong lang attribute"
    assert r.children == [parser.Text(source)], "bad children"


def test_self_closing_style():
    "http://code.pediapress.com/wiki/ticket/93"
    styles = parse("<b />bla").find(parser.Style)
    if not styles:
        return
    s = styles[0]
    assert s.children == [], "expected empty or no style node"


def test_timeline():
    """http://code.pediapress.com/wiki/ticket/86"""
    source = "\nthis is the timeline script!\n"
    r = parse("<timeline>%s</timeline>" % source).find(parser.Timeline)[0]
    print(r)
    assert r.children == [], "expected no children"
    assert r.caption == source, "bad script"


def test_nowiki_self_closing():
    """http://code.pediapress.com/wiki/ticket/102"""
    links = parse("<nowiki />[[foobar]]").find(parser.Link)
    assert links, EXPECTED_A_LINK


def test_nowiki_closing():
    """http://code.pediapress.com/wiki/ticket/102"""
    links = parse("</nowiki>[[foobar]]").find(parser.Link)
    assert links, EXPECTED_A_LINK


def test_math_stray():
    """http://code.pediapress.com/wiki/ticket/102"""
    links = parse("</math>[[foobar]]").find(parser.Link)
    assert links, EXPECTED_A_LINK

    links = parse("<math />[[foobar]]").find(parser.Link)
    assert links, EXPECTED_A_LINK


def test_math_basic():
    m = parse("<math>foobar</math>").find(parser.Math)[0]
    assert m.caption == "foobar"


def test_timeline_stray():
    """http://code.pediapress.com/wiki/ticket/102"""
    links = parse("</timeline>[[foobar]]").find(parser.Link)
    assert links, EXPECTED_A_LINK

    links = parse("<timeline />[[foobar]]").find(parser.Link)
    assert links, EXPECTED_A_LINK


def test_ftp_url():
    """http://code.pediapress.com/wiki/ticket/98"""

    def checkurl(url):
        urls = parse("foo %s bar" % url).find(parser.URL)
        assert urls, "expected a url"
        assert urls[0].caption == url, BAD_URL

        urls = parse("[%s bar]" % url).find(parser.NamedURL)
        assert urls, "expected a named url"
        assert urls[0].caption == url, BAD_URL

    checkurl("ftp://bla.com:8888/asdfasdf+ad'fdsf$fasd{}/~ralf?=blubb/@#&*(),blubb")
    checkurl("ftp://bla.com:8888/$blubb/")


def test_http_url():
    def checkurl(url):
        caption = parse(f"foo [{url}]").find(parser.NamedURL)[0].caption
        assert caption == url, "bad named url"

        caption = parse(url).find(parser.URL)[0].caption
        assert caption == url, BAD_URL

    checkurl("http://pediapress.com/'bla")
    checkurl("http://pediapress.com/bla/$/blubb")
    checkurl("http://pediapress.com/foo*bar")
    checkurl("http://pediapress.com/foo|bar")
    checkurl("http://pediapress.com/{curly_braces}")


def test_schemeless_url():
    url = "[//toolserver.org/~geohack/geohack.php?pagename=Benutzer%3AVolker.haas/Test&language=de&params=51.4213888889_N_9.64805555556_E_dim:100_region:DE-NI_type:waterbody&title=Namentlicher+Beginn+Weser]"

    caption = parse(url).find(parser.NamedURL)[0].caption
    assert caption == url[1:-1]


def test_source_vlist():
    r = parse("<source lang=c>int main()</source>").find(parser.TagNode)[0]
    assert r.vlist == {"lang": "c"}, f"bad value: {r.vlist!r}"


def test_not_pull_in_alpha_image():
    link = parse("[[Image:link.jpg|ab]]cd").find(parser.Link)[0]
    assert "cd" not in link.as_text(), "'cd' not in linkstext"


@pytest.mark.xfail
def test_pull_in_alpha():
    """http://code.pediapress.com/wiki/ticket/130"""
    link = parse("[[link|ab]]cd").find(parser.Link)[0]
    assert "cd" in link.as_text(), "'cd' not in linkstext"


def test_not_pull_in_numeric():
    link = parse("[[link|ab]]12").find(parser.Link)[0]

    assert "12" not in link.as_text(), "'12' in linkstext"


def test_section_consume_break():
    r = parse("= about us =\n\nfoobar").find(parser.Section)[0]
    txt = r.as_text()
    assert "foobar" in txt, "foobar should be inside the section"


def test_text_caption_none_bug():
    lst = parse("[[]]").find(parser.Text)
    print(lst)
    for x in lst:
        assert x.caption is not None


def test_link_inside_gallery():
    links = parse(
        "<gallery>Bild:Guanosinmonophosphat protoniert.svg|[[Guanosinmonophosphat]] <br /> (GMP)</gallery>",
        lang="de",
    ).find(parser.Link)
    print(links)
    assert len(links) == 2, "expected 2 links"


def test_indented_table():
    r = parse(':::{| class="prettytable" \n|-\n| bla || blub\n|}')
    style = r.find(parser.Style)[-1]
    tables = style.find(parser.Table)
    assert len(tables) == 1, "expected a table as child"


def test_double_exclamation_mark_in_table():
    r = parse("{|\n|-\n| bang!!\n| cell2\n|}\n")
    cells = r.find(parser.Cell)
    print("CELLS:", cells)
    assert len(cells) == 2, "expected two cells"
    txt = cells[0].as_text()
    print("TXT:", txt)
    assert "!!" in txt, 'expected "!!" in cell'


def test_table_row_exclamation_mark():
    r = parse(
        """{|
|-
! bgcolor="#ffccaa" | foo || bar
|}"""
    )
    cells = r.find(parser.Cell)
    print("CELLS:", cells)
    assert len(cells) == 2, "expected exactly two cells"


def test_unknown_tag():
    """http://code.pediapress.com/wiki/ticket/212"""
    r = parse("<nosuchtag>foobar</nosuchtag>")
    txt = r.as_text()
    print("TXT:", repr(txt))
    assert "<nosuchtag>" in txt, "opening tag missing in as_text()"
    assert "</nosuchtag>" in txt, "closing tag missing in as_text()"


# Test varieties of link


def test_plain_link():
    r = parse("[[bla]]").find(parser.ArticleLink)[0]
    assert r.target == "bla"


def test_piped_link():
    r = parse("[[bla|blubb]]").find(parser.ArticleLink)[0]
    assert r.target == "bla"
    assert r.children[0].caption == "blubb"


def test_category_link():
    r = parse("[[category:bla]]").find(parser.CategoryLink)[0]
    assert r.target == "category:bla", WRONG_TARGET
    assert r.namespace == 14, WRONG_NAMESPACE


def test_category_colon_link():
    r = parse("[[:category:bla]]").find(parser.SpecialLink)[0]
    assert r.target == "category:bla", WRONG_TARGET
    assert r.namespace == 14, WRONG_NAMESPACE
    assert not isinstance(r, parser.CategoryLink)


def test_image_link():
    t = uparser.parse_string("", "[[画像:Tajima mihonoura03s3200.jpg]]", lang="ja")
    r = t.find(parser.ImageLink)[0]
    assert r.target == "画像:Tajima mihonoura03s3200.jpg"
    assert r.namespace == 6, WRONG_NAMESPACE


def test_image_colon_link():
    r = parse("[[:image:bla.jpg]]").find(parser.SpecialLink)[0]
    assert r.target == "image:bla.jpg"
    assert r.namespace == 6, WRONG_NAMESPACE
    assert not isinstance(r, parser.ImageLink), "should not be an image link"


def test_interwiki_link():
    r = parse("[[wikt:bla]]").find(parser.InterwikiLink)[0]
    assert r.target == "wikt:bla", WRONG_TARGET
    assert r.namespace == "wikt", WRONG_NAMESPACE
    r = parse("[[mw:bla]]").find(parser.InterwikiLink)[0]
    assert r.target == "mw:bla", WRONG_TARGET
    assert r.namespace == "mw", WRONG_NAMESPACE


def test_language_link():
    r = parse("[[es:bla]]").find(parser.LangLink)[0]
    assert r.target == "es:bla", WRONG_TARGET
    assert r.namespace == "es", WRONG_NAMESPACE


def test_long_language_link():
    r = parse("[[csb:bla]]").find(parser.LangLink)[0]
    assert r.target == "csb:bla", WRONG_TARGET
    assert r.namespace == "csb", WRONG_NAMESPACE


def test_subpage_link():
    r = parse("[[/SomeSubPage]]").find(parser.ArticleLink)[0]
    assert r.target == "/SomeSubPage", WRONG_TARGET


@pytest.mark.xfail
def test_normalize():
    r = parse("[[MediaWiki:__bla_ _ ]]").find(parser.NamespaceLink)[0]
    assert r.target == "MediaWiki:__bla_ _ "
    assert r.namespace == 8


def test_quotes_in_tags():
    """http://code.pediapress.com/wiki/ticket/199"""
    vlist = parse("""<source attr="value"/>""").find(parser.TagNode)[0].vlist
    print("VLIST:", vlist)
    assert vlist == {"attr": "value"}, BAD_VLIST

    vlist = parse("""<source attr='value'/>""").find(parser.TagNode)[0].vlist
    print("VLIST:", vlist)
    assert vlist == {"attr": "value"}, BAD_VLIST


def test_imagemap():
    r = parse(
        """<imagemap>Image:Ppwiki.png| exmaple map|100px|thumb|left
    # this is a comment
    # rectangle half picture (left)
    rect 0 0 50 100 [[na| link description]]

    #circle top right
    circle 75 25 24 [http://external.link | just a other link desc]

    #poly bottom right
    poly 51 51 100 51 75 100 [[bleh| blubb]]
    </imagemap>
"""
    )
    assert r.children[0].tagname == "imagemap"


def test_bad_imagemap():
    """http://code.pediapress.com/wiki/ticket/572"""

    r = parse(
        """<imagemap>
foo bar baz
</imagemap>"""
    )
    assert r.children[0].tagname == "imagemap"
    assert "foo bar baz" in r.children[0].imagemap.image


def test_link_with_quotes():
    """http://code.pediapress.com/wiki/ticket/303"""
    r = parse("[[David O'Leary]]")
    link = r.find(parser.ArticleLink)[0]
    assert link.target == "David O'Leary", "Link target not fully detected"


def test_no_tab_removal():
    d = DummyDB()
    r = uparser.parse_string(title="", raw="\ttext", wikidb=d)
    assert not r.find(parser.PreFormatted), "unexpected PreFormatted node"


def test_nowiki_inside_tags():
    """http://code.pediapress.com/wiki/ticket/366"""

    s = """<span style="color:<nowiki>#</nowiki>DF6108;">foo</span>"""
    r = parse(s)
    tags = r.find(parser.TagNode)
    print("tags:", tags)
    assert tags, "no tag node found"
    tag = tags[0]
    print("vlist:", tag.vlist)
    assert tag.vlist == {"style": {"color": "#DF6108"}}, BAD_VLIST


def test_misformed_tag():
    s = '<div"barbaz">bold</div>'
    r = parse(s).find(parser.TagNode)
    assert len(r) == 1, "expected a TagNode"


def test_p_tag():
    s = "<p>para1</p><p>para2</p>"
    r = parse(s).find(parser.Paragraph)
    print("PARAGRAPHS:", r)
    assert len(r) == 2, "expected 2 paragraphs"


def test_table_style_parsing_1():
    """http://code.pediapress.com/wiki/ticket/172"""
    s = '{| class="prettytable"\n|-\n|blub\n|align="center"|+bla\n|}\n'
    r = parse(s)
    cells = r.find(parser.Cell)
    print("VLIST:", cells[1].vlist)
    assert cells[1].vlist == {"align": "center"}, BAD_VLIST


def test_table_style_parsing_jtalbot():
    """mentioned in http://code.pediapress.com/wiki/ticket/172,
    but real issue is:
    http://code.pediapress.com/wiki/ticket/366
    """
    s = "{| \n|-\n| cell 1 <ref>this|| not cell2</ref>\n|}\n"
    r = parse(s)
    cells = r.find(parser.Cell)
    assert len(cells) == 1, EXPECTED_EXACTLY_ONE_CELL


def test_force_close_1():
    s = """{|
|-
| <ul><li>bla</li>
| bla 2
|-
| bla 3
| bla 4
|}
"""
    r = parse(s)
    cells = r.find(parser.Cell)
    print("CELLS:", cells)
    assert len(cells) == 4, "expected 4 cells"


@pytest.mark.xfail
def test_force_close_code():
    s = "before <code>inside<code> after"
    r = parse(s)

    tagnodes = r.find(parser.TagNode)
    assert len(tagnodes) == 1, "expected exactly one tagnode"
    txt = tagnodes.as_text()
    print("TXT:", txt)
    assert "after" not in txt


def test_force_close_section_in_li():
    """example from http://code.pediapress.com/wiki/ticket/63"""
    s = """<ul><li>item
== section 1 ==
baz
"""
    r = parse(s)
    items = r.find(parser.Item)
    assert len(items) == 1, "epxected one item"
    sections = items[0].find(parser.Section)
    assert len(sections) == 1, "expected exactly one section inside li"


def test_namedurl_inside_list():
    r = parse("* [http://pediapress.com pediapress]")
    urls = r.find(parser.NamedURL)
    assert len(urls) == 1, "expected exactly one NamedURL"


def test_link_in_sectiontitle():
    r = parse("== [[mainz]] ==")
    links = r.find(parser.Link)
    assert len(links) == 1, "expected exactly one link"


def test_table_whitespace_before_cell():
    r = parse(
        """
{|
|-
 | bgcolor="#aacccc" | cell1
| cell2
|}
"""
    )
    cells = r.find(parser.Cell)
    print("CELLS:", cells)
    assert len(cells) == 2, "expected exactly 3 cells"
    print("VLIST:", cells[0].vlist)
    assert cells[0].vlist == {"bgcolor": "#aacccc"}


def test_table_whitespace_before_row():
    r = parse(
        """
{|
  |- bgcolor="#aacccc"
| | cell1
| cell2
|}
"""
    )
    rows = r.find(parser.Row)
    print("ROWS:", rows)
    assert len(rows) == 1, "expected exactly one row"
    print("VLIST:", rows[0].vlist)
    assert rows[0].vlist == {"bgcolor": "#aacccc"}


def test_table_whitespace_before_begintable():
    def check(s):
        r = parse(s)
        tables = r.find(parser.Table)
        assert len(tables) == 1, "expected exactly one table"
        assert tables[0].vlist == {"bgcolor": "#aacccc"}

    check(
        """
 {| bgcolor="#aacccc"
|-
| cell1
| cell2
|}
"""
    )

    check(
        """
:::{| bgcolor="#aacccc"
|-
| cell1
| cell2
|}
"""
    )


def test_closing_td_in_cell():
    r = parse(
        """
{|
<td>foo</td>
|}"""
    )
    cell = r.find(parser.Cell)[0]
    assert "td" not in cell.as_text()


def test_i_tag():
    r = parse("<i>i</i>")
    s = r.find(parser.Style)[0]
    assert s.caption == "''"


def test_em_tag():
    r = parse("<em>i</em>")
    s = r.find(parser.Style)[0]
    assert s.caption == "''"


def test_big_tag():
    r = parse("<big>i</big>")
    s = r.find(parser.Style)[0]
    assert s.caption == "big"


def test_small_tag():
    r = parse("<small>i</small>")
    s = r.find(parser.Style)[0]
    assert s.caption == "small"


def test_sup_tag():
    r = parse("<sup>i</sup>")
    s = r.find(parser.Style)[0]
    assert s.caption == "sup"


def test_sub_tag():
    r = parse("<sub>i</sub>")
    s = r.find(parser.Style)[0]
    assert s.caption == "sub"


def test_cite_tag():
    r = parse("<cite>i</cite>")
    s = r.find(parser.Style)[0]
    assert s.caption == "cite"


def test_u_tag():
    r = parse("<u>i</u>")
    s = r.find(parser.Style)[0]
    assert s.caption == "u"


def test_strong_tag():
    r = parse("<strong>i</strong>")
    s = r.find(parser.Style)[0]
    assert s.caption == "'''"


def test_hr_tag():
    r = parse("<hr>")
    s = r.find(parser.TagNode)[0]
    assert s.caption == "hr"


def test_hr_line():
    r = parse("------------")
    s = r.find(parser.TagNode)[0]
    assert s.caption == "hr"


def test_broken_link():
    r = parse("[[Image:|bla]]")
    links = r.find(parser.Link)
    assert not links, "expected no links"


def test_broken_link_whitespace():
    r = parse("[[Image:   |bla]]")
    links = r.find(parser.Link)
    assert not links, "expected no links"


def test_comment_inside_nowiki():
    comment = "this is a comment"
    s = expand_str("<pre><!-- this is a comment --></pre>")
    assert comment in s
    r = parse(s)
    txt = r.as_text()
    assert "this is a comment" in txt


def test_imagemod_space_px():
    """http://code.pediapress.com/wiki/ticket/475"""
    r = parse("[[Image:Thales foo.jpg|400 px|right]]")
    img = r.find(parser.ImageLink)[0]
    txt = img.as_text()
    assert "px" not in txt, "should contain no children"


def test_imagemod_upright():
    """http://code.pediapress.com/wiki/ticket/459"""

    def doit(s, expected):
        up = parse(s, lang="de").find(parser.ImageLink)[0].upright
        assert up == expected, f"expected {expected} got {up}"

    doit("[[Datei:bla.jpg|upright|thumb|foobar]]", 0.75)
    doit("[[Datei:bla.jpg|upright=0.5|thumb|foobar]]", 0.5)


def test_imagemod_localised_magicwords():
    magicwords = [
        {"aliases": ["center", "foobar"], "case-sensitive": "", "name": "img_center"},
    ]

    def parsei(s, magicwords):
        res = uparser.parse_string(title="test", raw=s, magicwords=magicwords)
        img = res.find(parser.ImageLink)[0]
        return img

    r = parsei("[[Image:bla.jpg|foobar]]", magicwords)
    assert r.align == "center"


def test_paragraph_vs_italic():
    """http://code.pediapress.com/wiki/ticket/514"""
    r = parse("<i>first italic\n\nstill italic</i>")
    styles = r.find(parser.Style)
    txt = " ".join([x.as_text() for x in styles])
    assert "first italic" in txt
    assert "still italic" in txt
    paras = r.find(parser.Paragraph)
    assert len(paras) == 2


def test_pull_in_styletags_1():
    s = "<b> one\n\n== two ==\n\nthree\n</b>\nfour\n"
    r = uparser.simpleparse(s)
    styles = r.find(parser.Style)
    txt = " ".join(x.as_text() for x in styles)
    assert "one" in txt
    assert "two" in txt
    assert "three" in txt
    assert "four" not in txt


def test_magicwords():
    txt = parse("__NOTOC__").as_text()
    print(txt)
    assert "NOTOC" not in txt

    txt = parse("__NOTOC____NOEDITSECTION__").as_text()
    print(txt)
    assert "NOTOC" not in txt

    txt = parse("__NOINDEX__").as_text()
    print(txt)
    assert "NOINDEX" not in txt

    txt = parse("__NOGLOSSARY__").as_text()
    print(txt)
    assert "NOGLOSSARY" not in txt


def test_vlist_newline():
    def check(txt):
        tag = parse(txt).find(parser.TagNode)[0]
        assert tag.vlist, "vlist should not be empty"

    check('<ref\n\nname="bla">bla</ref>')
    check('<ref\n\nname\n\n=\n\n"bla">bla</ref>')
    check('<ref\n\nname\n\n=\n\n"bla\n">bla</ref>')


def test_span_vs_ref():
    s = """<ref><span>bla</ref> after"""
    r = parse(s)
    spans = [x for x in r.find(parser.TagNode) if x.tagname == "span"]
    print("SPAN:", spans)
    span = spans[0]
    txt = span.as_text()
    assert "after" not in txt


def test_double_source():
    """http://code.pediapress.com/wiki/ticket/536"""
    s = """
<source lang=c>int main</source>
between
<source lang=c>int main2</source>
"""
    r = parse(s)
    nodes = [x for x in r.find(parser.TagNode) if x.tagname == "source"]
    print(nodes)
    assert len(nodes) == 2


def test_style_tags_vlist():
    s = """
<font color="#00C000">green</font>
"""
    ftag = parse(s).find(parser.TagNode)[0]
    print(ftag)
    assert ftag.vlist


def test_stray_tag():
    s = "abc</div>def"
    txt = parse(s).as_text()
    print(txt)
    assert "div" not in txt, "stray tag in output"
