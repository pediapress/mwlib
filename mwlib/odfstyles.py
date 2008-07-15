#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (c) 2008, PediaPress GmbH
# See README.txt for additional licensing information.

# http://books.evc-cit.info/odbook/ch03.html#char-para-styling-section

from odf import style, text

# we define some styles here -----------------------------------------------------------------------------

arial =  style.FontFace(name="Arial", fontfamily="Arial", fontfamilygeneric="swiss", fontpitch="variable")
# Paragraph styles
standard = style.Style(name="Standard", family="paragraph")
standard.addElement(style.ParagraphProperties(marginbottom="0cm", margintop="0cm" ))
ArticleHeader = style.Style(name="Heading 1", family="paragraph", defaultoutlinelevel="1")
ArticleHeader.addElement(style.TextProperties(attributes={'fontsize':"28pt", 'fontweight':"bold"}))
h1 = style.Style(name="Heading 1", family="paragraph", defaultoutlinelevel="1")
h1.addElement(style.TextProperties(attributes={'fontsize':"24pt", 'fontweight':"bold"}))
h2 = style.Style(name="Heading 2", family="paragraph", defaultoutlinelevel="2")
h2.addElement(style.TextProperties(attributes={'fontsize':"22pt", 'fontweight':"bold"}))
h3 = style.Style(name="Heading 3", family="paragraph", defaultoutlinelevel="3")
h3.addElement(style.TextProperties(attributes={'fontsize':"20pt", 'fontweight':"bold"}))
h4 = style.Style(name="Heading 4", family="paragraph", defaultoutlinelevel="4")
h4.addElement(style.TextProperties(attributes={'fontsize':"18pt", 'fontweight':"bold"}))
h5 = style.Style(name="Heading 5", family="paragraph", defaultoutlinelevel="5")
h5.addElement(style.TextProperties(attributes={'fontsize':"16pt", 'fontweight':"bold"}))
h6 = style.Style(name="Heading 6", family="paragraph", defaultoutlinelevel="6")
h6.addElement(style.TextProperties(attributes={'fontsize':"14pt", 'fontweight':"bold"}))
textbody = style.Style(name="Text body", family="paragraph", parentstylename=standard)
textbody.addElement(style.ParagraphProperties(
        attributes={'marginbottom':"0cm", 'margintop':"0cm",'textalign':"left"}))
subtitle = style.Style(name="Subtitle", family="paragraph", nextstylename=textbody)
subtitle.addElement(style.ParagraphProperties(textalign="center") )
subtitle.addElement(style.TextProperties(fontsize="14pt", fontstyle="italic", fontname="Arial"))
title = style.Style(name="Title", family="paragraph", nextstylename=subtitle)
title.addElement(style.ParagraphProperties(textalign="center") )
title.addElement(style.TextProperties(fontsize="18pt", fontweight="bold", fontname="Arial"))

#graphic = style.Style(name="Graphic", family="presentation")
graphic = style.Style(name="Graphic", family="graphic")
graphic.addElement(style.GraphicProperties(wrap="dynamic", verticalrel="paragraph", horizontalrel="paragraph"))
graphic.addElement(
    style.GraphicProperties(padding="0.15in",borderleft="none",borderright="0.0154in double #FFFFFF",
                            bordertop="0.0154in double #FFFFFF",borderbottom="0.0154in double #FFFFFF"))

#graphic = style.Style(name="Graphic", family="graphic")
#graphic.addElement(style.GraphicProperties(runthrough="foreground", wrap="dynamic", numberwrappedparagraphs="no-limit",
#                                           verticalpos="top", verticalrel="page",horizontalpos="center", horizontalrel="page"))



fixed = style.Style(name="Fixed", family="paragraph")
fixed.addElement(style.TextProperties(attributes={'fontpitch':"fixed"}))

# ----- math ----
"""
  <style:style style:name="Formula" style:family="graphic">
   <style:graphic-properties text:anchor-type="as-char" svg:y="0in" fo:margin-left="0.0791in" fo:margin-right="0.0791in" style:vertical-pos="middle" style:vertical-rel="text"/>
  </style:style>
and

 <office:automatic-styles>
  <style:style style:name="fr1" style:family="graphic" style:parent-style-name="Formula">
   <style:graphic-properties style:vertical-pos="middle" style:vertical-rel="text" draw:ole-draw-aspect="1"/>
  </style:style>
 </office:automatic-styles>

                (DRAWNS,u'auto-grow-height'),
                (DRAWNS,u'auto-grow-width'),


"""

formula = style.Style(name="Formula", family="graphic")
#formula.addElement(style.GraphicProperties(attributes={"anchortype":"as-char" ,"y":"0in","marginleft":"0.0791in","marginright":"0.0791in","verticalpos":"middle","verticalrel":"text", "oledrawaspect":"1"}))
#formula.addElement(style.GraphicProperties(verticalpos="middle",verticalrel="baseline",  minwidth="0.7902in", autogrowheight="1", autogrowwidth="1"))

sect  = style.Style(name="Sect1", family="section")


preformatted = style.Style(name="Preformatted",family="paragraph")
preformatted.addElement(
    style.ParagraphProperties(marginleft=".25in",marginright=".25in", margintop=".25in",marginbottom=".25in", backgroundcolor="#e6e6e6"))
preformatted.addElement(style.TextProperties(attributes={"fontname":"DejaVu Sans Mono", "fontsize":"8pt"}))



hr = style.Style(name="HorizontalLine", family="paragraph")
hr.addElement(style.ParagraphProperties(margintop="0in",marginbottom="0.1965in",borderlinewidthbottom="0.0008in 0.0138in 0.0008in",padding="0in",borderleft="none",borderright="none",bordertop="none",borderbottom="0.0154in double #808080"))


# inline Text styles ---------------------------------------------
# small big sub sup var deleted inserted  strike underline overline  center 
emphasis = style.Style(name="Emphasis",family="text")
emphasis.addElement(style.TextProperties(fontstyle="italic")) # shpould be also bold, but is paresed differntly
italic = emphasis
strong = style.Style(name="Bold",family="text")
#strong.addElement(style.TextProperties(fontstyle="bold"))
strong.addElement(style.TextProperties(fontweight="bold"))
bold = strong
sup = style.Style(name="Sup", family="text")
sup.addElement(style.TextProperties(attributes={'textposition':"super"}))
sub = style.Style(name="Sub", family="text")
sub.addElement(style.TextProperties(attributes={'textposition':"-30% 50%"}))
underline = style.Style(name="Underline", family="text")
underline.addElement(style.TextProperties(attributes={'textunderlinestyle':"solid"}))

overline = underline # FIXME
small = standard # FIXME
big = standard # FIXME
var = standard # FIXME
strike = standard # FIXME
deleted = standard # FIXME
inserted = standard # FIXME

# paragraph text styles

# indented  cite code source  blockquote  preformatted teletyped

center = style.Style(name="Center", family="paragraph")
center.addElement(style.ParagraphProperties(attributes={'textalign':"center"}))

indented = style.Style(name="Indented", family="paragraph")
indented.addElement(style.ParagraphProperties(attributes={'marginleft':"0.12in"}))

blockquote = style.Style(name="Blockquote", family="paragraph")
blockquote.addElement(style.ParagraphProperties(attributes={'marginleft':"0.12in",'marginright':"0.12in"}))

cite = style.Style(name="Cite", family="text")
cite.addElement(style.TextProperties(attributes={'fontpitch':"fixed", "fontname":"DejaVu Sans Mono"}))
teletyped = cite # FIXME

code = source = preformatted 



dumbcolumn = style.Style(name="Dumbcolumn", family="table-column") # REALLY FIXME
dumbcolumn.addElement(style.TableColumnProperties(attributes={'columnwidth':"1.0in"}))

numberedlist = text.ListStyle(name="numberedlist")
numberedlist.addElement(text.ListLevelStyleNumber(level="1", numprefix="  ", numsuffix=".  ", numformat="1"))
numberedlist.addElement(text.ListLevelStyleNumber(level="2", numprefix="  ", numsuffix=")  ", numformat="a"))
numberedlist.addElement(text.ListLevelStyleBullet(level="3", numprefix="  ", numsuffix="   ", bulletchar=u'•'))

unorderedlist = text.ListStyle(name="unorderedlist")
unorderedlist.addElement(text.ListLevelStyleBullet(level="1",numprefix="   ", bulletchar=u'•', numsuffix="   "))

definitionlist = text.ListStyle(name="definitionlist")
definitionlist.addElement(text.ListLevelStyleBullet(level="1", bulletchar=' ', numsuffix=""))

definitionterm = style.Style(name="definitionterm", family="paragraph")
definitionterm.addElement(style.TextProperties(fontweight="bold"))



def applyStylesToDoc(doc):
    doc.fontfacedecls.addElement(arial)
    doc.styles.addElement(standard)
    doc.styles.addElement(dumbcolumn)
    doc.styles.addElement(indented)
    doc.styles.addElement(blockquote)
    doc.styles.addElement(ArticleHeader)
    doc.styles.addElement(fixed)
    doc.styles.addElement(cite)
    doc.styles.addElement(underline)
    doc.styles.addElement(sup)
    doc.styles.addElement(sub)
    doc.styles.addElement(center)
    doc.styles.addElement(formula)
    doc.styles.addElement(h1)
    doc.styles.addElement(h2)
    doc.styles.addElement(h3)
    doc.styles.addElement(h4)
    doc.styles.addElement(h5)
    doc.styles.addElement(h6)
    doc.automaticstyles.addElement(sect)
    doc.styles.addElement(textbody)
    doc.styles.addElement(subtitle)
    doc.styles.addElement(title)
    #doc.styles.addElement(photo)
    doc.styles.addElement(graphic)
    doc.styles.addElement(strong)
    doc.styles.addElement(emphasis)
    doc.styles.addElement(preformatted)
    doc.styles.addElement(hr)
    doc.styles.addElement(numberedlist)
    doc.styles.addElement(unorderedlist)
    doc.styles.addElement(definitionlist)
    doc.styles.addElement(definitionterm)




def test(fn):

    from odf.opendocument import OpenDocumentText
    #from odf.style import Header
    #from odf.text import P, Section, Span, Chapter, H
    from odf import text

    textdoc = OpenDocumentText()
    applyStylesToDoc(textdoc)
    tdoc = textdoc.text
    
    
    # headings
    for i,s in enumerate((h1,h2,h3,h4,h5)):
        i+=1
        t = text.H(outlinelevel=i, stylename=s, text="Heading %d" % i)
        tdoc.addElement(t)

    # preformatted
    p = text.P(stylename=preformatted)
    p.addText(u"This")
    p.addElement(text.LineBreak())
    p.addText(u"Is")
    p.addElement(text.Tab())
    p.addText(u"PreFormatted    d    d                      d")
    p.addElement(text.LineBreak())
    p.addText(u"very long lineeeee"*30) # DOES NOT WORK
    tdoc.addElement(p)

    # fixed
    p = text.P(stylename=fixed)
    p.addText("This is fixed 1234 width, continued with HR")
    tdoc.addElement(p)

    # hr
    p = text.P(stylename=hr)
    tdoc.addElement(p)

    p = text.P(stylename=textbody)
    tdoc.addElement(p)
    
    # strong
    t = text.Span(stylename=strong)    
    t.addText("this is strong")
    p.addElement(t)
    p.addText(" ")

    # italic
    t = text.Span(stylename=italic)    
    t.addText("this is italic")
    p.addElement(t)

    # strong italic FIXME
    p.addText(" ")
    t = text.Span(stylename=strong)    
    p.addElement(t)
    t2 = text.Span(stylename=italic)    
    t2.addText("is this bold italic?")
    t.addElement(t2)
    p.addText(" ")

    # underline FIXME
    t = text.Span(stylename=underline)    
    t.addText("this is underline")
    p.addElement(t)
    p.addText(" ")

    # sub FIXME
    t = text.Span(stylename=sub)    
    t.addText("this is sub")
    p.addElement(t)
    p.addText(" ")

    # sup FIXME
    t = text.Span(stylename=sup)    
    t.addText("this is sup")
    p.addElement(t)


    textdoc.save(fn)


if __name__ == "__main__":
    import sys
    fn = sys.argv[1]
    test(fn)
    

