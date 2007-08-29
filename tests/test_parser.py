#! /usr/bin/env py.test

import sys
from mwlib import dummydb, parser, scanner


def parse(raw):    
    db = dummydb.DummyDB()
    
    tokens = scanner.tokenize("unknown", raw)
    r=parser.Parser(tokens, "unknown").parse()
    parser.show(sys.stdout, r, 0)
    return r

    
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
    images = [x for x in r.allchildren() if isinstance(x, parser.ImageLink)]

    assert len(images)==2

    for i in images:
        print "-->Image:", i, i.isInline()




def test_self_closing_nowiki():
    parse(u"<nowiki/>")
    parse(u"<nowiki  />")
    parse(u"<nowiki       />")
    parse(u"<NOWIKI>[. . .]</NOWIKI>")
