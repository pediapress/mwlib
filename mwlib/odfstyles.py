#! /usr/bin/env python
# -*- coding: utf-8 -*-
# See README.txt for additional licensing information.
#
#  This file defines the styles for odfwriter.py
#  This file mainly connects
#
# See odpy: 
# and the od* spec: http://docs.oasis-open.org/office/v1.1/OS/OpenDocument-v1.1-html/OpenDocument-v1.1.html
#



from odf import style
from odf import text

#CONTENT:
#
# Font styles: dejaVuSerif, dejaVuSerif, dejaVuSerif, dejaVuSansMono
#
# Section styles: sect
#          FIXME:  n/a
#
# Paragraph styles: standard, textbody, definitionterm, hr, center, blockquote
#                   indentedSingle, indentedDouble, indentedTriple, imgCaption, tableCaption
#            FIXME: standard vs textbody, 
#
# Text styles: emphasis, italic, strong, bold, sub, sup, underline, 
#              strike, big, small, var, deleted, inserted, cite (?),
#       FIXME:  overline (there is no overline in ooo Writer), teletyped
#
# Table styles: 
#        FIXME: dumbcolumn
#
# List styles: numberedlist, unorderedlist, definitionlist
#
# Header styles: ArticleHeader, h0-h5
#         FIXME: Rename h0-h5
#
# Graphic styles: frmOuter, frmInner, frmOuterRight, frmOuterLeft, frmOuterCenter,
#          FIXME: formula



#
# Font Styles
# see http://books.evc-cit.info/odbook/ch03.html#char-para-styling-section for a fast introdution
#
dejaVuSerif = style.FontFace(
        name="DejaVuSerif",fontfamily="'DejaVu Serif'", fontfamilygeneric="roman", fontpitch="variable")
dejaVuSans = style.FontFace(
        name="DejaVuSans", fontfamily="'DejaVu Sans'", fontfamilygeneric="swiss", fontpitch="variable")
dejaVuMono = style.FontFace(
        name="DejaVumono",fontfamily="'DejaVu mono'",fontfamilygeneric="modern", fontpitch="fixed")
dejaVuSansMono = style.FontFace(
        name="DejaVuSansMono", fontfamily="'DejaVu Sans Mono'", fontfamilygeneric="swiss", fontpitch="fixed")

#
# Section styles 
#
sect  = style.Style(name="Sect1", family="section")
sectTable = style.Style(name="SectTable", family="section")

#
# Paragraph styles
#
standard = style.Style(name="Standard", family="paragraph")
standard.addElement(
    style.ParagraphProperties(
            margintop="0in", marginbottom="0in",
            punctuationwrap="hanging", linebreak="strict"
    )
)
standard.addElement(
    style.TextProperties(
        color="#000000", fontsize="12pt", fontname="DejaVuSerif",
        language="en", country="US"
    )
)

# textbody is the default for text
textbody = style.Style(name="TextBody", family="paragraph")
textbody.addElement(
    style.ParagraphProperties(
        marginbottom="0.05in", margintop="0.04in", textalign="left"
    )
)
textbody.addElement(
    style.TextProperties(
        color="#000000", fontsize="12pt", language="en", country="US",
        fontname="DejaVuSerif"
    )
)

#
# special paragraph styles:  paragraph text styles
#
preformatted = style.Style(name="Preformatted",family="paragraph")
preformatted.addElement(
    style.ParagraphProperties(
        marginleft=".25in", marginright=".25in", margintop=".25in", marginbottom=".25in", 
        backgroundcolor="#e6e6e6"
    )
)
preformatted.addElement(
    style.TextProperties(
                fontname="DejaVumono", 
                fontsize="10pt"
        )
)


definitionterm = style.Style(name="definitionterm", family="paragraph")
definitionterm.addElement(
    style.TextProperties(
        fontweight="bold",
        fontname="DejaVuSerif"
    )
)



hr = style.Style(name="HorizontalLine", family="paragraph")
hr.addElement(
    style.ParagraphProperties(
        margintop="0in", marginbottom="0.1965in",padding="0in",
        borderlinewidthbottom="0.0008in 0.0138in 0.0008in", 
        borderleft="none",borderright="none",bordertop="none",
        borderbottom="0.0154in double #808080"
    )
)

tableCaption = style.Style(name="TableCaption", family="paragraph")
tableCaption.addElement(
    style.ParagraphProperties(
        textalign="center",
        marginbottom="0.1in"
    )
)
tableCaption.addElement(
    style.TextProperties(
        fontweight="bold",
        fontname="DejaVuSerif"
    )
)


center = style.Style(name="Center", family="paragraph")
center.addElement(
    style.ParagraphProperties(
        textalign="center"
    )
)
center.addElement(
    style.TextProperties(
        fontname="DejaVuSerif"
    )
)

blockquote = style.Style(name="Blockquote", family="paragraph")
blockquote.addElement(
    style.ParagraphProperties(
        marginleft="0.12in",marginright="0.12in", margintop="0in",marginbottom="0.15in"
    )
)
blockquote.addElement(
    style.TextProperties(
        fontname="DejaVuSerif"
    )
)


indentedSingle = style.Style(name="IndentedSingle", family="paragraph")
indentedSingle.addElement(
    style.ParagraphProperties(
        marginleft="0.12in"
    )
)
indentedSingle.addElement(
    style.TextProperties(
        fontname="DejaVuSerif"
    )
)

indentedDouble = style.Style(name="IndentedDouble", family="paragraph")
indentedDouble.addElement(
    style.ParagraphProperties(
        marginleft="0.24in"
    )
)
indentedDouble.addElement(
    style.TextProperties(
        fontname="DejaVuSerif"
    )
)

indentedTriple = style.Style(name="IndentedTriple", family="paragraph")
indentedTriple.addElement(
    style.ParagraphProperties(
        marginleft="0.36in"
    )
)
indentedTriple.addElement(
    style.TextProperties(
        fontname="DejaVuSerif"
    )
)

#
# Text styles (inline)
#
emphasis = style.Style(name="Emphasis",family="text")
emphasis.addElement(
    style.TextProperties(
        fontstyle="italic", fontname="DejaVuSerif"
    )
) # should be also bold, but is paresed differntly

italic = emphasis #alternative name

strong = style.Style(name="Bold",family="text")
strong.addElement(
    style.TextProperties(
        fontweight="bold", fontname="DejaVuSerif"
    )
)
bold = strong #alternative name

sup = style.Style(name="Sup", family="text")
sup.addElement(
    style.TextProperties(
        textposition="super", fontname="DejaVuSerif"
    )
)

sub = style.Style(name="Sub", family="text") 
sub.addElement(
    style.TextProperties(
        textposition="-30% 50%", fontname="DejaVuSerif"
    )
)

underline = style.Style(name="Underline", family="text")
underline.addElement(
    style.TextProperties(
        textunderlinestyle="solid", fontname="DejaVuSerif"
    )
)

strike =  style.Style(name="Strike", family="text")
strike.addElement(
    style.TextProperties(
        textlinethroughstyle="solid", fontname="DejaVuSerif"
    )
)

big = style.Style(name="Big", family="text")
big.addElement(
    style.TextProperties(
        fontsize="125%", fontname="DejaVuSerif"
    )
)


small = style.Style(name="Small", family="text")
small.addElement(
    style.TextProperties(
        fontsize="80%", fontname="DejaVuSerif"
    )
)

teletyped = style.Style(name="Teletyped", family="text")
teletyped.addElement(
    style.TextProperties(
                fontname="DejaVumono", fontsize="80%"
        )
)


# logical text tags:
var = emphasis 
cite = emphasis
deleted = strike
inserted = underline
code = teletyped
source = preformatted

overline = textbody # try to FIXME, but there is no overline in ooo Writer




#
# Table styles
#

dumbcolumn = style.Style(name="Dumbcolumn", family="table-column") # REALLY FIXME
dumbcolumn.addElement(style.TableColumnProperties(attributes={'columnwidth':"1.0in"}))

#
# List styles
#

##2do: testcases
#ordered list (until lvl2, then bullets)
numberedlist = text.ListStyle(name="numberedlist")
numberedlist.addElement(
    text.ListLevelStyleNumber(
        level="1", numprefix="  ", numsuffix=".  ", numformat="1"
    )
)
numberedlist.addElement(
    text.ListLevelStyleNumber(
        level="2", numprefix="  ", numsuffix=")  ", numformat="a"
    )
)
numberedlist.addElement(
    text.ListLevelStyleBullet(
        level="3", numprefix="  ", numsuffix="   ", bulletchar=u'•'
    )
)


# unordered list
unorderedlist = text.ListStyle(name="unorderedlist")
unorderedlist.addElement(
    text.ListLevelStyleBullet(
        level="1",numprefix="   ", bulletchar=u'•', numsuffix="   "
    )
)


definitionlist = text.ListStyle(name="definitionlist")
definitionlist.addElement(
    text.ListLevelStyleBullet(
        level="1", bulletchar=' ', numsuffix=""
    )
)


#
# Header Syles
#

ArticleHeader = style.Style(name="HeadingArticle", family="paragraph", defaultoutlinelevel="1")
ArticleHeader.addElement(
    style.ParagraphProperties(
            margintop="0in",marginbottom="0.15in"
    )
)
ArticleHeader.addElement(
    style.TextProperties(
        fontsize="24pt", fontname="DejaVuSans"
    )
)

h0 = ArticleHeader
"""
h0 = style.Style(name="Heading0", family="paragraph", defaultoutlinelevel="1")
h0.addElement(
    style.ParagraphProperties(
        margintop="0.3in",marginbottom="0.15in"
    )
)
h0.addElement(
    style.TextProperties(
        fontsize="24pt", fontname="DejaVuSans"
    )
)
"""

h1 = style.Style(name="Heading1", family="paragraph", defaultoutlinelevel="2")
h1.addElement(
    style.ParagraphProperties(
        margintop="0.3in",marginbottom="0.15in"
    )
)
h1.addElement(
    style.TextProperties(
        fontsize="20pt", fontname="DejaVuSans"
    )
)


h2 = style.Style(name="Heading2", family="paragraph", defaultoutlinelevel="3")
h2.addElement(
    style.TextProperties(
        fontsize="18pt", fontweight="bold", fontname="DejaVuSans"
    )
)
h2.addElement(
    style.ParagraphProperties(
        margintop="0.3in",marginbottom="0.08in"
    )
)


h3 = style.Style(name="Heading3", family="paragraph", defaultoutlinelevel="4")
h3.addElement(
    style.TextProperties(
        fontsize="16pt", fontweight="bold", fontname="DejaVuSans"
    )
)
h3.addElement(
    style.ParagraphProperties(
        margintop="0.3in",marginbottom="0.05in"
    )
)


h4 = style.Style(name="Heading4", family="paragraph", defaultoutlinelevel="5")
h4.addElement(
    style.TextProperties(
        fontsize="14pt", fontweight="bold", fontname="DejaVuSans"
    )
)
h4.addElement(
    style.ParagraphProperties(
        margintop="0.3in",marginbottom="0.05in"
    )
)


h5 = style.Style(name="Heading5", family="paragraph", defaultoutlinelevel="6")
h5.addElement(
    style.TextProperties(
        fontsize="10pt", fontweight="bold", fontname="DejaVuSans"
    )
)
h5.addElement(
    style.ParagraphProperties(
        margintop="0.3in",marginbottom="0.05in"
    )
)


# the text under a image
imgCaption = style.Style(name="ImageCaption", family="paragraph", parentstylename=textbody)
imgCaption.addElement(
    style.ParagraphProperties(
        textalign="center", justifysingleword="false" 
    )
)
imgCaption.addElement(
    style.TextProperties(
        color="#000000", fontsize="10pt", fontname="DejaVuSerif",
        language="en", country="US"))





#
# Graphic styles:
#
##2do: where is grafic used?
##fixme: clean it
#graphic = style.Style(name="Graphic", family="graphic")
#graphic.addElement(style.GraphicProperties(wrap="dynamic", verticalrel="paragraph", horizontalrel="paragraph"))
#graphic.addElement(
#    style.GraphicProperties(padding="0.15in",borderleft="none",borderright="0.0154in double #FFFFFF",
#                            bordertop="0.0154in double #FFFFFF",borderbottom="0.0154in double #FFFFFF"))

#graphic.addElement(style.GraphicProperties(padding="0.15in", border="0.01in single #ff00ff"))
#graphic = style.Style(name="Graphic", family="graphic")
#graphic.addElement(style.GraphicProperties(runthrough="foreground", wrap="dynamic", numberwrappedparagraphs="no-limit",
#                                           verticalpos="top", verticalrel="page",horizontalpos="center", horizontalrel="page"))




# define a outer frame:
# frmOuter and frmInner mainy used to format and align the images

frmOuter = style.Style(name="mwlibfrmOuter", family="graphic")
frmStyGraPropDef = style.GraphicProperties(
        marginleft="0.1in", marginright="0.1in", margintop="0.1in", marginbottom="0.1in",
        wrap="right", numberwrappedparagraphs="no-limit", 
        verticalpos="from-top", horizontalpos="from-left", 
        verticalrel="paragraph", horizontalrel="paragraph", 
        backgroundcolor="transparent", 
        padding="0.0402in", border="0.0138in solid #c0c0c0", shadow="none")
frmOuter.addElement(frmStyGraPropDef)
frmOuter.internSpacing = 0.2 
# if frmOuter has marginleft/marginright set this float-value to the sum: internSpacing = marginleft + marginright

# frmOuterRight, frmOuterLeft and frmOuterCenter are like frmOuter, but need other alignment
frmOuterRight = style.Style(name="mwlibfrmOuterRight", family="graphic", parentstylename=frmOuter) # does not inherit GrapficPorpertys!
frmStyGraPropRight = style.GraphicProperties(
        marginleft="0.1in", marginright="0.1in", margintop="0.1in", marginbottom="0.1in",
        numberwrappedparagraphs="no-limit", 
        verticalpos="from-top", 
        verticalrel="paragraph", horizontalrel="paragraph", 
        backgroundcolor="transparent", 
        padding="0.0402in", border="0.0138in solid #c0c0c0", shadow="none",
        horizontalpos="right", wrap="left"
)
frmOuterRight.addElement(frmStyGraPropRight)

frmOuterLeft = style.Style(name="mwlibfrmOuterLeft", family="graphic", parentstylename=frmOuter) 
frmStyGraProbLeft = style.GraphicProperties(
        marginleft="0.1in", marginright="0.1in", margintop="0.1in", marginbottom="0.1in",
        numberwrappedparagraphs="no-limit", 
        verticalpos="from-top", 
        verticalrel="paragraph", horizontalrel="paragraph", 
        backgroundcolor="transparent", 
        padding="0.0402in", border="0.0138in solid #c0c0c0", shadow="none",
        horizontalpos="left", wrap="right"
)
frmOuterLeft.addElement(frmStyGraProbLeft)

frmOuterCenter = style.Style(name="mwlibfrmOuterCenter", family="graphic", parentstylename=frmOuter) 
frmStyGraPropCenter = style.GraphicProperties(
        marginleft="0.1in", marginright="0.1in", margintop="0.1in", marginbottom="0.1in",
        numberwrappedparagraphs="no-limit", 
        verticalpos="from-top", 
        verticalrel="paragraph", horizontalrel="paragraph", 
        backgroundcolor="transparent", 
        padding="0.0402in", border="0.0138in solid #c0c0c0", shadow="none",
        horizontalpos="center", wrap="paralell"
)
frmOuterCenter.addElement(frmStyGraPropCenter)


# the inner frame
frmInner = style.Style(name="mwlib_frmInner", family="graphic")
frmInner.addElement(
    style.GraphicProperties(
        verticalpos="from-top", horizontalpos="center",
        verticalrel="paragraph", horizontalrel="paragraph",
        mirror="none", clip="rect(0in 0in 0in 0in)",
        luminance="0%", contrast="0%", red="0%", green="0%", blue="0%", 
        gamma="100%", colorinversion="false", imageopacity="100%", colormode="standard"
    )
)

##fixme: fixed not used
#fixed = style.Style(name="Fixed", family="paragraph")
#fixed.addElement(style.TextProperties(attributes={'fontpitch':"fixed"}))



##fixme: forumlars are still broken
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






def applyStylesToDoc(doc):
    doc.fontfacedecls.addElement(dejaVuSerif)
    doc.fontfacedecls.addElement(dejaVuSans)
    doc.fontfacedecls.addElement(dejaVuMono)
    doc.fontfacedecls.addElement(dejaVuSansMono)
    
    #doc.styles.addElement(defStyleParagraph)
    
    doc.styles.addElement(standard)
    doc.styles.addElement(dumbcolumn)
    doc.styles.addElement(indentedSingle)
    doc.styles.addElement(indentedDouble)
    doc.styles.addElement(indentedTriple)
    doc.styles.addElement(strike)
    doc.styles.addElement(big)
    doc.styles.addElement(small)
    doc.styles.addElement(blockquote)
    doc.styles.addElement(ArticleHeader)
    #doc.styles.addElement(fixed)
    doc.styles.addElement(cite)
    doc.styles.addElement(underline)
    doc.styles.addElement(sup)
    doc.styles.addElement(sub)
    doc.styles.addElement(center)
    doc.styles.addElement(teletyped)
    doc.styles.addElement(formula)
    doc.styles.addElement(h0)
    doc.styles.addElement(h1)
    doc.styles.addElement(h2)
    doc.styles.addElement(h3)
    doc.styles.addElement(h4)
    doc.styles.addElement(h5)
    doc.automaticstyles.addElement(sect)
    doc.styles.addElement(textbody)
    #doc.styles.addElement(subtitle)
    #doc.styles.addElement(title)
    #doc.styles.addElement(photo)
    #doc.styles.addElement(graphic)
    doc.styles.addElement(strong)
    doc.styles.addElement(emphasis)
    doc.styles.addElement(preformatted)
    doc.styles.addElement(code)
    doc.styles.addElement(source)
    doc.styles.addElement(hr)
    doc.styles.addElement(numberedlist)
    doc.styles.addElement(unorderedlist)
    doc.styles.addElement(definitionlist)
    doc.styles.addElement(definitionterm)
    
    doc.styles.addElement(frmOuterCenter)
    doc.styles.addElement(frmOuterLeft)
    doc.styles.addElement(frmOuterRight)
    doc.styles.addElement(frmInner)
    doc.styles.addElement(imgCaption)
    doc.styles.addElement(tableCaption)
    doc.styles.addElement(sectTable)

