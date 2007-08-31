#! /usr/bin/env py.test
# -*- coding: utf-8 -*-

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

    #r=parse(u'{| cellspacing="2" border="0" cellpadding="3" bgcolor="#EFEFFF" width="100%"\n|-\n| width="12%" bgcolor="#EEEEEE"| 9. Juli 2006\n| width="13%" bgcolor="#EEEEEE"| Berlin\n| width="20%" bgcolor="#EEEEEE"| [[Bild:flag of Italy.svg|30px]] \'\'\'Italien\'\'\'\n| width="3%" bgcolor="#EEEEEE"| \u2013\n| width="20%" bgcolor="#EEEEEE"| [[Bild:flag of France.svg|30px]] Frankreich\n| width="3%" bgcolor="#EEEEEE"|\n| width="25%" bgcolor="#EEEEEE"| [[Fu\xdfball-Weltmeisterschaft 2006/Finalrunde#Finale: Italien .E2.80.93 Frankreich 6:4 n. E..2C 1:1 n. V. .281:1.2C 1:1.29|6:4 n. E., (1:1, 1:1, 1:1)]]\n|}\n')


    r=parse(u"""{{Begriffsklarungshinweis}}
{{Infobox Ort in Deutschland
|Art                = Stadt
|Wappen             = Wappen-stadt-bonn.svg
|lat_deg            = 50 |lat_min = 44 |lat_sec = 02.37
|lon_deg            =  7 |lon_min = 5 |lon_sec = 59.33
|Bundesland         = Nordrhein-Westfalen
|Regierungsbezirk   = Köln
|Landkreis          = Kreisfreie Stadt
|Höhe               = 60
|Fläche             = 141.22
|Einwohner          = 314301 
|Stand              = 2007-06-31
|PLZ                = 53111–53229
|PLZ-alt            = 5300
|Vorwahl            = 0228
|Kfz                = BN
|Gemeindeschlüssel  = 05 3 14 000
|NUTS               = DEA22
|LOCODE             = DE BON
|Gliederung         = 4 [[Stadtbezirk]]e mit 51 [[Ortsteil]]en
|Adresse-Verband    = Berliner Platz 2<br />53111 Bonn
|Website            = [http://www.bonn.de/ www.bonn.de]
|Bürgermeister      = [[Bärbel Dieckmann]]
|Bürgermeistertitel = [[Oberbürgermeister]]in
|Partei             = SPD
}}

Die [[Bundesstadt]] '''Bonn''' liegt im Süden von [[Nordrhein-Westfalen]] an beiden Ufern des [[Rhein]]s. Die Stadt kann auf eine mehr als 2000-jährige Geschichte zurückschauen und gehört zu den ältesten Städten in Deutschland. Bis zum Ende des 18.&nbsp;Jahrhunderts war Bonn [[Residenz]] der [[Kurköln|Kölner Kurfürsten]]. Hier kam 1770 [[Ludwig van Beethoven]] zur Welt. Im Laufe des 19.&nbsp;Jahrhunderts entwickelte sich die [[Rheinische Friedrich-Wilhelms-Universität Bonn|Universität]] zu einer der bedeutendsten deutschen Hochschulen.

Von 1949 bis 1990 war Bonn [[Bundeshauptstadt|Hauptstadt]] und bis 1999 [[Regierungssitz]] der Bundesrepublik Deutschland.<!-- Durch den Einigungsvertrag wurde Berlin am 3. Oktober 1990 Hauptstadt --> Nach dem Umzug von [[Deutscher Bundestag|Parlament]] und Teilen der [[Bundesregierung (Deutschland)|Bundesregierung]] nach [[Berlin]] haben in der „[[Bundesstadt]]“ sechs [[Bundesministerium (Deutschland)|Bundesministerien]] ihren ersten Dienstsitz, die anderen einen Zweitsitz.

Im [[Bundesviertel]] wurde im Juli 2006 der „[[UN-Campus]]“ eröffnet. Dort ist ein Großteil der 13 in Bonn ansässigen Organisationen der [[Vereinte Nationen|Vereinten Nationen (UN)]] untergebracht. Neben UN-Organisationen prägen die [[Museumsmeile]], Verwaltungsgebäude großer deutscher Unternehmen, das Funkhaus der „[[Deutsche Welle|Deutschen Welle]]“ und das „[[World Conference Center Bonn]]“ diesen Teil der Stadt. """)

    
    images = [x for x in r.allchildren() if isinstance(x, parser.ImageLink)]

    assert len(images)==2

    for i in images:
        print "-->Image:", i, i.isInline()




def test_self_closing_nowiki():
    parse(u"<nowiki/>")
    parse(u"<nowiki  />")
    parse(u"<nowiki       />")
    parse(u"<NOWIKI>[. . .]</NOWIKI>")
