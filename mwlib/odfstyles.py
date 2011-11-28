#! /usr/bin/env python
# -*- coding: utf-8 -*-
# See README.rst for additional licensing information.
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
#            FIXME: footnote (liststyle does not work)
#
# Text styles: emphasis, italic, strong, bold, sub, sup, underline, 
#              strike, big, small, var, deleted, inserted, cite (?),
#       FIXME:  overline (there is no overline in ooo Writer), teletyped
#
# Table styles: 
#        FIXME: dumbcolumn
#
# List styles: numberedlist, unorderedlist, definitionlist
#       FIXME: <not reviewed yet>
#
# Header styles: ArticleHeader, h0-h5
#         FIXME: Rename h0-h5
#
# Graphic styles: frmOuter, frmInner, frmOuterRight, frmOuterLeft, frmOuterCenter,
#          FIXME: formula, imageMap
#
# General FIXME: add "style:display-name" for each element

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


# textbody is the default for text
textbody = style.Style(name="TextBody", family="paragraph")
textbody.addElement(
    style.ParagraphProperties(
        marginbottom="0.05in", margintop="0.04in", textalign="left",
        punctuationwrap="hanging", linebreak="strict",
        orphans="3", keeptogether="always",

    )
)
textbody.addElement(
    style.TextProperties(
        fontsize="12pt", language="en", country="US",
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
        backgroundcolor="#e6e6e6",
        orphans="3", keeptogether="always",
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
        marginleft="0.12in",marginright="0.12in", margintop="0in",marginbottom="0.15in",
        orphans="3", keeptogether="always"
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
        marginleft="0.12in", marginright="0in", margintop="0.05in", marginbottom="0.04in",
        orphans="3", keeptogether="always"
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
        marginleft="0.24in", marginright="0in", margintop="0.05in", marginbottom="0.04in",
        orphans="3", keeptogether="always"
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
        marginleft="0.36in", marginright="0in", margintop="0.05in", marginbottom="0.04in",
        orphans="3", keeptogether="always"
    )
)
indentedTriple.addElement(
    style.TextProperties(
        fontname="DejaVuSerif"
    )
)


footnote = style.Style(name="Footnote", family="paragraph", liststylename="FootnoteList") #fixme: liststyle does not work
footnote.addElement(
    style.TextProperties(
        fontsize="10pt", fontname="DejaVuSerif"
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
        fontsize="80%", fontname="DejaVumono"
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
#footnote list ##fixme: does not work
footnoteLLSN = text.ListLevelStyleNumber(
        level="1", numformat="1"
)

footnoteLLSN.addElement(
    style.ListLevelProperties(
        spacebefore="0.02in", minlabelwidth="0.2in"
    )
)
footnotelist = text.ListStyle(name="FootnoteList")
footnotelist.addElement(footnoteLLSN)

#
# Header Syles
#

ArticleHeader = style.Style(name="HeadingArticle", family="paragraph", defaultoutlinelevel="1")
ArticleHeader.addElement(
    style.ParagraphProperties(
            margintop="0in",marginbottom="0.15in", keepwithnext="always"
    )
)
ArticleHeader.addElement(
    style.TextProperties(
        fontsize="24pt", fontname="DejaVuSans"
    )
)

h0 = ArticleHeader #alternative name


chapter = style.Style(name="Chapter", family="paragraph", defaultoutlinelevel="1")
chapter.addElement(
    style.ParagraphProperties(
        margintop="0.3in",marginbottom="0.15in", keepwithnext="always"
    )
)
chapter.addElement(
    style.TextProperties(
        fontsize="32pt", fontname="DejaVuSans"
    )
)



h1 = style.Style(name="Heading1", family="paragraph", defaultoutlinelevel="2")
h1.addElement(
    style.ParagraphProperties(
        margintop="0.3in",marginbottom="0.15in", keepwithnext="always"
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
        fontsize="18pt", fontname="DejaVuSans"
    )
)
h2.addElement(
    style.ParagraphProperties(
        margintop="0.3in",marginbottom="0.08in", keepwithnext="always"
    )
)


h3 = style.Style(name="Heading3", family="paragraph", defaultoutlinelevel="4")
h3.addElement(
    style.TextProperties(
        fontsize="16pt", fontname="DejaVuSans"
    )
)
h3.addElement(
    style.ParagraphProperties(
        margintop="0.3in",marginbottom="0.05in", keepwithnext="always"
    )
)


h4 = style.Style(name="Heading4", family="paragraph", defaultoutlinelevel="5")
h4.addElement(
    style.TextProperties(
        fontsize="14pt", fontname="DejaVuSans"
    )
)
h4.addElement(
    style.ParagraphProperties(
        margintop="0.3in",marginbottom="0.05in", keepwithnext="always"
    )
)


h5 = style.Style(name="Heading5", family="paragraph", defaultoutlinelevel="6")
h5.addElement(
    style.TextProperties(
        fontsize="10pt", fontname="DejaVuSans"
    )
)
h5.addElement(
    style.ParagraphProperties(
        margintop="0.3in",marginbottom="0.05in", keepwithnext="always"
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
        fontsize="10pt", fontname="DejaVuSerif",
    )
)

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
# frmOuter and frmInner are mainy used to format and align the images

frmOuter = style.Style(name="mwlibfrmOuter", family="graphic")
frmStyGraPropDef = style.GraphicProperties(
        marginleft="0.1in", marginright="0.1in", margintop="0.1in", marginbottom="0.1in",
        wrap="right", numberwrappedparagraphs="no-limit", 
        verticalpos="from-top", horizontalpos="from-left", 
        verticalrel="paragraph", horizontalrel="paragraph", 
        backgroundcolor="transparent", 
        padding="0.0402in", border="0.0138in solid #c0c0c0", 
        shadow="none"
)
frmOuter.addElement(frmStyGraPropDef)
frmOuter.internSpacing = 0.2 
# if frmOuter has marginleft/marginright set this float-value to the sum: internSpacing = marginleft + marginright

# frmOuterRight, frmOuterLeft and frmOuterCenter are like frmOuter, but need other alignment
frmOuterRight = style.Style(name="mwlibfrmOuterRight", family="graphic", parentstylename=frmOuter) # does not inherit GrapficPorpertys!
frmStyGraPropRight = style.GraphicProperties(
        marginleft="0.1in", marginright="0.1in", margintop="0.1in", marginbottom="0.1in",
        wrap="left", numberwrappedparagraphs="no-limit", 
        verticalpos="from-top", horizontalpos="right",
        verticalrel="paragraph", horizontalrel="paragraph", 
        backgroundcolor="transparent", 
        padding="0.0402in", border="0.0138in solid #c0c0c0", 
        shadow="none"
)
frmOuterRight.addElement(frmStyGraPropRight)

frmOuterLeft = style.Style(name="mwlibfrmOuterLeft", family="graphic", parentstylename=frmOuter) 
frmStyGraProbLeft = style.GraphicProperties(
        marginleft="0.1in", marginright="0.1in", margintop="0.1in", marginbottom="0.1in",
        wrap="right", numberwrappedparagraphs="no-limit", 
        verticalpos="from-top", horizontalpos="left",
        verticalrel="paragraph", horizontalrel="paragraph", 
        backgroundcolor="transparent", 
        padding="0.0402in", border="0.0138in solid #c0c0c0",
        shadow="none"
)
frmOuterLeft.addElement(frmStyGraProbLeft)

frmOuterCenter = style.Style(name="mwlibfrmOuterCenter", family="graphic", parentstylename=frmOuter) 
frmStyGraPropCenter = style.GraphicProperties(
        marginleft="0.1in", marginright="0.1in", margintop="0.1in", marginbottom="0.1in",
        wrap="paralell", numberwrappedparagraphs="no-limit", 
        verticalpos="from-top", horizontalpos="center", 
        verticalrel="paragraph", horizontalrel="paragraph", 
        backgroundcolor="transparent", 
        padding="0.0402in", border="0.0138in solid #c0c0c0",
        shadow="none"
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



##2do: imagemap is still in progress
imageMap = style.Style(name="frmImageMap", family="graphic")
"""imageMap.addElement(
    style.GraphicProperties(
        zindex="0"
    )
)
imageMap.addElement(
    style.TextProperties(
        anchortype="paragraph"
    )
)"""



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

    for font in [dejaVuSerif,
                 dejaVuSans,
                 dejaVuMono,
                 dejaVuSansMono,
                 ]:
        doc.fontfacedecls.addElement(font)

    doc.automaticstyles.addElement(sect)

    for style in [dumbcolumn,
                  indentedSingle,
                  indentedDouble,
                  indentedTriple,
                  strike,
                  big,
                  small,
                  blockquote,
                  ArticleHeader,
                  cite,
                  underline,
                  sup,
                  sub,
                  center,
                  teletyped,
                  formula,
                  chapter,
                  h0,
                  h1,
                  h2,
                  h3,
                  h4,
                  h5,
                  sectTable,
                  textbody,
                  strong,
                  emphasis,
                  preformatted,
                  code,
                  source,
                  footnotelist,
                  footnote,
                  hr,
                  numberedlist,
                  unorderedlist,
                  definitionlist,
                  definitionterm,
                  frmOuterCenter,
                  frmOuterLeft,
                  frmOuterRight,
                  frmInner,
                  imgCaption,
                  tableCaption,
                  sectTable,]:
        doc.styles.addElement(style)

