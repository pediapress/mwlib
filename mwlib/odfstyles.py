#! /usr/bin/env python

# Copyright (c) 2008, PediaPress GmbH
# See README.txt for additional licensing information.

# http://books.evc-cit.info/odbook/ch03.html#char-para-styling-section

from odf import style

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
        attributes={'marginbottom':"0.212cm", 'margintop':"0cm",'textalign':"justify", 'justifysingleword':"false"}))
subtitle = style.Style(name="Subtitle", family="paragraph", nextstylename=textbody)
subtitle.addElement(style.ParagraphProperties(textalign="center") )
subtitle.addElement(style.TextProperties(fontsize="14pt", fontstyle="italic", fontname="Arial"))
title = style.Style(name="Title", family="paragraph", nextstylename=subtitle)
title.addElement(style.ParagraphProperties(textalign="center") )
title.addElement(style.TextProperties(fontsize="18pt", fontweight="bold", fontname="Arial"))

photo = style.Style(name="MyMaster-photo", family="presentation")

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

"""

formula = style.Style(name="Formula", family="graphic")
formula.addElement(style.GraphicProperties(attributes={"anchortype":"as-char" ,"y":"0in","marginleft":"0.0791in","marginright":"0.0791in","verticalpos":"middle","verticalrel":"text", "oledrawaspect":"1"}))
sect  = style.Style(name="Sect1", family="section")
#sect.addElement(style.SectionProperties(backgroundcolor="#e6e6e6"))



# inline Text styles ---------------------------------------------
# small big sub sup var deleted inserted  strike underline overline  center 
emphasis = style.Style(name="Emphasis",family="text")
emphasis.addElement(style.TextProperties(fontstyle="italic")) # shpould be also bold, but is paresed differntly
italic = emphasis
strong = style.Style(name="Bold",family="text")
strong.addElement(style.TextProperties(fontsize="14pt", fontweight="bold"))
bold = strong
sup = style.Style(name="Sup", family="paragraph")
sup.addElement(style.TextProperties(attributes={'textposition':"super"}))
sub = style.Style(name="Sub", family="paragraph")
sub.addElement(style.TextProperties(attributes={'textposition':"-30% 50%"}))
underline = style.Style(name="Underline", family="paragraph")
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

cite = style.Style(name="Cite", family="paragraph")
cite.addElement(style.ParagraphProperties(attributes={'marginleft':"0.12in",'marginright':"0.12in"}))
cite.addElement(style.TextProperties(attributes={'fontpitch':"fixed"}))

code = source = preformatted = teletyped = cite # FIXME

dumbcolumn = style.Style(name="Dumbcolumn", family="table-column") # REALLY FIXME
dumbcolumn.addElement(style.TableColumnProperties(attributes={'columnwidth':"1.0in"}))


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
    doc.styles.addElement(photo)
