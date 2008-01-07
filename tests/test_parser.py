#! /usr/bin/env py.test

# Copyright (c) 2007, PediaPress GmbH
# See README.txt for additional licensing information.

from mwlib import dummydb, parser, expander, uparser
from mwlib.expander import DictDB

parse = uparser.simpleparse
    
def test_headings():
    r=parse(u"""
= 1 =
== 2 ==
= 3 =
""")
    
    sections = [x.children[0].asText() for x in r.children if isinstance(x, parser.Section)]
    assert sections == [u" 1 ", u" 3 "]


def test_style():
    r=parse(u"'''mainz'''")
    s=r.children[0].children[0]
    assert isinstance(s, parser.Style)
    assert s.caption == "'''"

def test_single_quote_after_style():
    """http://code.pediapress.com/wiki/ticket/20"""
    
    r=parse(u"''pp'''s")
    styles = r.find(parser.Style)
    assert len(styles)==1, "should be pp's"
    
    
    s=r.children[0].children[0]
    assert isinstance(s, parser.Style)
    assert s.caption == "'''"
    

def test_links_in_style():
    r=parse(u"'''[[mainz]]'''")
    s=r.children[0].children[0]
    assert isinstance(s, parser.Style)
    assert isinstance(s.children[0], parser.Link)
    


def test_parse_image_inline():
    #r=parse("[[Bild:flag of Italy.svg|30px]]")
    #img = [x for x in r.allchildren() if isinstance(x, parser.ImageLink)][0]
    #print "IMAGE:", img, img.isInline()

    r=parse(u'{| cellspacing="2" border="0" cellpadding="3" bgcolor="#EFEFFF" width="100%"\n|-\n| width="12%" bgcolor="#EEEEEE"| 9. Juli 2006\n| width="13%" bgcolor="#EEEEEE"| Berlin\n| width="20%" bgcolor="#EEEEEE"| [[Bild:flag of Italy.svg|30px]] \'\'\'Italien\'\'\'\n| width="3%" bgcolor="#EEEEEE"| \u2013\n| width="20%" bgcolor="#EEEEEE"| [[Bild:flag of France.svg|30px]] Frankreich\n| width="3%" bgcolor="#EEEEEE"|\n| width="25%" bgcolor="#EEEEEE"| [[Fu\xdfball-Weltmeisterschaft 2006/Finalrunde#Finale: Italien .E2.80.93 Frankreich 6:4 n. E..2C 1:1 n. V. .281:1.2C 1:1.29|6:4 n. E., (1:1, 1:1, 1:1)]]\n|}\n')
    images = r.find(parser.ImageLink)

    assert len(images)==2

    for i in images:
        print "-->Image:", i, i.isInline()


def test_parse_image_6():
    """http://code.pediapress.com/wiki/ticket/6"""
    r=parse("[[Bild:img.jpg|thumb|+some text]] [[Bild:img.jpg|thumb|some text]]")

    images = r.find(parser.ImageLink)
    assert len(images)==2
    print images
    assert images[0].isInline() == images[1].isInline()


def test_self_closing_nowiki():
    parse(u"<nowiki/>")
    parse(u"<nowiki  />")
    parse(u"<nowiki       />")
    parse(u"<NOWIKI>[. . .]</NOWIKI>")



def test_break_in_li():
    r=parse("<LI> foo\n\n\nbla")
    tagnode = r.find(parser.TagNode)[0]
    assert hasattr(tagnode, "starttext")
    assert hasattr(tagnode, "endtext")


def test_switch_default():

    db=DictDB(
        Bonn="""{{Infobox
|Bundesland         = Nordrhein-Westfalen
}}
""",
        Infobox="""{{#switch: {{{Bundesland}}}
        | Bremen = [[Bremen (Land)|Bremen]]
        | #default = [[{{{Bundesland|Bayern}}}]]
}}
""")

    te = expander.Expander(db.getRawArticle("Bonn"), pagename="thispage", wikidb=db)
    res = te.expandTemplates()

    
    print "EXPANDED:", repr(res)
    assert "Nordrhein-Westfalen" in res

def test_pipe_table():

    db=DictDB(Foo="""
bla
{{{ {{Pipe}}}
blubb
""",
                   Pipe="|")

    te = expander.Expander(db.getRawArticle("Foo"), pagename="thispage", wikidb=db)
    res = te.expandTemplates()

    
    print "EXPANDED:", repr(res)
    assert "bla" in res
    assert "blubb" in res

def test_pipe_begin_table():

    db=DictDB(Foo="""
bla
{{{Pipe}} |}
blubb
""",
              Pipe="|")

    te = expander.Expander(db.getRawArticle("Foo"), pagename="thispage", wikidb=db)
    res = te.expandTemplates()
    
    
    print "EXPANDED:", repr(res)
    assert "bla" in res
    assert "blubb" in res
    assert "{|" in res



def test_cell_parse_bug():
    """http://code.pediapress.com/wiki/ticket/17"""
    r=parse("""{|
|-
[[Image:bla.png|bla]]
|}""")
    print r
    
    images = r.find(parser.ImageLink)
    assert images

def test_table_not_eating():
    """internal parser error.
    http://code.pediapress.com/wiki/ticket/32
    http://code.pediapress.com/wiki/ticket/29    
"""
    uparser.simpleparse("""{|)
|10<sup>10<sup>100</sup></sup>||gsdfgsdfg
|}""")

def test_table_not_eating2():
    """internal parser error.
    http://code.pediapress.com/wiki/ticket/32
    http://code.pediapress.com/wiki/ticket/29    
"""
    uparser.simpleparse("""{| 
<tr><td>'''Birth&nbsp;name'''</td><td colspan="2">Alanis Nadine Morissette</td></tr><tr><td>'''Born'''</td>
|}
""")


def test_parse_comment():
    ex = """foo
<!-- comment --->
bar"""

    def check(node):
        paras = node.find(parser.Paragraph)
        assert len(paras)==1, 'expected exactly one paragraph node'
    
    check(parse(ex))
    check(parse(expander.expandstr(ex)))

def test_nowiki_entities():
    """http://code.pediapress.com/wiki/ticket/40"""
    node = parse("<nowiki>&amp;</nowiki>")
    txt = node.find(parser.Text)[0]
    assert txt.caption==u'&', "expected an ampersand"

def test_blockquote_with_newline():
    """http://code.pediapress.com/wiki/ticket/41"""
    node = parse("<blockquote>\nblockquoted</blockquote>").find(parser.Style)[0]
    print "STYLE:", node
    assert "blockquoted" in node.asText(), "expected 'blockquoted'"

def test_table_style(): 
    """http://code.pediapress.com/wiki/ticket/39. thanks xyb."""
    
    def check(s):
        r = parse(s)
        t=r.find(parser.Table)[0]
        print t
        assert t.vlist['width'] == u'80%', "got wrong value %r" % (t.vlist['width'],)


    check('{| class="toccolours" width="80%" |}')
    check('{| class="toccolours" width=80% |}')

def test_ol_ul():
    """http://code.pediapress.com/wiki/ticket/33"""

    r=parse("#num\n*bul\n")
    lists = r.find(parser.ItemList)    
    assert len(lists)==2

    r=parse("*num\n#bul\n")
    lists = r.find(parser.ItemList)    
    assert len(lists)==2
