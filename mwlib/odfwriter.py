#! /usr/bin/env python

# Copyright (c) 2008, PediaPress GmbH
# See README.txt for additional licensing information.
"""
This is initial code for an ODF writer.

The code is based on xhtmlwriter.py

all write-methods need to be prefixed with 'o' like owriteParagraph.
those prefixed with 'x' are unmodofied copies from xhtmlwriter.py 
and deactived.

ToDo:

 * fix parse tree (blockelements)
 * implement missing methods
 * add missing styles

"""
import sys

import odf
from odf.opendocument import OpenDocumentText
from odf import style, text, dc, meta
from mwlib import parser,  mathml
from mwlib.log import Log
import advtree 

log = Log("odfwriter")

def showNode(obj):
    attrs = obj.__dict__.keys()
    log(obj.__class__.__name__ ) 
    stuff =  ["%s => %r" %(k,getattr(obj,k)) for k in attrs if 
              (not k == "children") and getattr(obj,k)
              ]
    if stuff:
        log(repr(stuff))

# we define some styles here -----------------------------------------------------------------------------

arial =  style.FontFace(name="Arial", fontfamily="Arial", fontfamilygeneric="swiss", fontpitch="variable")
# Paragraph styles
standardstyle = style.Style(name="Standard", family="paragraph")
standardstyle.addElement(style.ParagraphProperties(marginbottom="0cm", margintop="0cm" ))
h1style = style.Style(name="Heading 1", family="paragraph", defaultoutlinelevel="1")
h1style.addElement(style.TextProperties(attributes={'fontsize':"20pt", 'fontweight':"bold"}))
textbodystyle = style.Style(name="Text body", family="paragraph", parentstylename=standardstyle)
textbodystyle.addElement(style.ParagraphProperties(
        attributes={'marginbottom':"0.212cm", 'margintop':"0cm",'textalign':"justify", 'justifysingleword':"false"}))
subtitlestyle = style.Style(name="Subtitle", family="paragraph", nextstylename=textbodystyle)
subtitlestyle.addElement(style.ParagraphProperties(textalign="center") )
subtitlestyle.addElement(style.TextProperties(fontsize="14pt", fontstyle="italic", fontname="Arial"))
titlestyle = style.Style(name="Title", family="paragraph", nextstylename=subtitlestyle)
titlestyle.addElement(style.ParagraphProperties(textalign="center") )
titlestyle.addElement(style.TextProperties(fontsize="18pt", fontweight="bold", fontname="Arial"))
# Text styles
emphasisstyle = style.Style(name="Emphasis",family="text")
emphasisstyle.addElement(style.TextProperties(fontstyle="italic"))
sectstyle  = style.Style(name="Sect1", family="section")
sectstyle.addElement(style.SectionProperties(backgroundcolor="#e6e6e6"))


def applyStylesToDoc(doc):
    doc.fontfacedecls.addElement(arial)
    doc.styles.addElement(standardstyle)
    doc.styles.addElement(h1style)
    doc.automaticstyles.addElement(sectstyle)
    doc.styles.addElement(textbodystyle)
    doc.styles.addElement(subtitlestyle)
    doc.styles.addElement(titlestyle)
    doc.styles.addElement(emphasisstyle)
    


class ODFWriter(object):
    namedLinkCount = 1

    def __init__(self, language="en", namespace="en.wikipedia.org", creator="", license="GFDL", imagesrcresolver=None):
        self.language = language
        self.namespace = namespace
        self.imagesrcresolver = imagesrcresolver # e.g. "http://anyhost/redir?img=IMAGENAME" where IMAGENAME is substituted
        self.references = []
        self.doc =  OpenDocumentText()
        applyStylesToDoc(self.doc)
        self.text = self.doc.text

        if creator:
            self.doc.meta.addElement(meta.InitialCreator(text=creator))
            self.doc.meta.addElement(dc.Creator(text=creator))
        if language is not None:
            self.doc.meta.addElement(dc.Language(text=language))
        if license is not None:
            self.doc.meta.addElement(meta.UserDefined(name="Rights", text=license))


        
        
    def getDoc(self, debuginfo=""):
        return self.doc

    
    def writeText(self, obj, parent):
        try:
            parent.addText(obj.caption)
        except odf.element.IllegalText:
            print obj, "not allowed in ", parent.type



    def write(self, obj, parent=None):
        #showNode(obj)
        # if its text, append to last node
        if isinstance(obj, parser.Text):
            self.writeText(obj, parent)
        else:
            # check for method
            m = "owrite" + obj.__class__.__name__
            m=getattr(self, m, None)
            
            if m: # find handler
                e = m(obj)
            else:
                #log("SKIPPED")
                #showNode(obj)
                e = None
            
            if e is None:
                e = parent
            
            for c in obj.children[:]:
                ce = self.write(c,e)
                if ce is not None and ce is not e:                    
                    #e.append(ce)
                    try: 
                        e.addElement(ce)
                    except odf.element.IllegalChild:
                        print ce.type, "not allowed in ", e.type
                        #e.parentNode.addElement(ce)
                        
            return e


    def owriteArticle(self, a):
        if a.caption:
            self.doc.meta.addElement(dc.Title(text=a.caption))
        return self.doc.text # mhm 

    def owriteSection(self, obj):
        title = obj.children[0].children[0].caption 
        level = 1 + obj.getLevel()
        r = text.Section(stylename=sectstyle, name=title) #, display="none")
        r.addElement(text.H(outlinelevel=level, stylename=h1style, text=title))
        obj.children = obj.children[1:]
        return r

    def owriteParagraph(self, obj):
        return text.P(stylename=textbodystyle)
        
    def owriteItem(self, item):
        
        li =text.ListItem()
        p = text.P(stylename=textbodystyle)
        li.addElement(p)
        
        def _addText(text):
            p.addText(text)

        li.addText = _addText
        
        return li

    def owriteItemList(self, lst):
        if lst.numbered:
            tag = "ol"
        else:
            tag = "ul"
        return text.List(stylename=textbodystyle)





# - unimplemented methods copy from xhtml writer ---------------------------------------------------

    def xwriteLink(self, obj): # FIXME (known|unknown)
        a = ET.Element("a")
        if obj.target:
            a.set("href", obj.target)
            a.set("class", "mwx.link.article")
        if not obj.children:
            a.text = obj.target
        return a


        
    def xwriteNode(self, n):
        pass # simply write children


    def xwriteCell(self, cell):
        td = ET.Element("td")
        self.setVList(td, cell)           
        return td
            
    def xwriteRow(self, row):
        return ET.Element("tr")

    def xwriteTable(self, t):           
        table = ET.Element("table")
        self.setVList(table, t)           
        if t.caption:
            c = ET.SubElement(table, "caption")
            self.writeText(t.caption, c)
        return table


    def setVList(self, element, node):
        """
        sets html attributes as found in the wikitext
        if this method is used it should be called *after* 
        the class attribute is set to some mwx.value.
        """
        if hasattr(node, "vlist") and node.vlist:
            print "vlist", element, node
            saveclass = element.get("class")
            for k,v in self.xserializeVList(node.vlist):
                element.set(k,v)
            if saveclass and element.get("class") != saveclass:
                element.set("class", " ".join((saveclass, element.get("class"))))

    def xserializeVList(self,vlist):
        args = [] # list of (key, value)
        styleArgs = []
        gotClass = 0
        gotExtraClass = 0
        for (key,value) in vlist.items():
            if isinstance(value, (basestring, int)):
                args.append((key, unicode(value)))
            if isinstance(value, dict) and key=="style":
                for (_key,_value) in value.items():
                    styleArgs.append("%s:%s" % (_key, _value))
                args.append(("style", '{%s}' % ','.join(styleArgs)))

        return args


    def xwriteReference(self, t):
        self.references.append(t)
        t =  ET.Element("sup")
        t.set("class", "mwx.reference")
        t.text = unicode( len(self.references))
        return t
        
    def xwriteReferenceList(self, t):
        if not self.references:
            return
        ol = ET.Element("ol")
        ol.set("class", "mwx.references")
        for i,r in enumerate(self.references):
            li = ET.SubElement(ol,"li")
            for x in r:                    
                self.write(x, li)                          
        self.references = []            
        return ol


    # Special Objects


    def xwriteTimeline(self, obj): 
        s = ET.Element("object")
        s.set("class", "mwx.timeline")
        s.set("type", "application/mediawiki-timeline")
        s.set("src", "data:text/plain;charset=utf-8,%s" % obj.caption)
        em = ET.SubElement(s, "em")
        em.set("class", "mwx.timeline.alternate")
        em.text = u"Timeline"
        return s

    def xwriteHiero(self, obj): # FIXME parser support
        s = ET.Element("object")
        s.set("class", "mwx.hiero")
        s.set("type", "application/mediawiki-hiero")
        s.set("src", "data:text/plain;charset=utf-8,%s" % obj.caption)
        em = ET.SubElement(s, "em")
        em.set("class", "mwx.hiero.alternate")
        em.text = u"Hiero"
        return s

    def xwriteMath(self, obj): 
        """
        this won't validate as long as we are using xhtml 1.0 transitional

        see also: http://www.mozilla.org/projects/mathml/authoring.html
        """
        s = ET.Element("object")
        s.set("class", "mwx.math")
        s.set("type", "application/mediawiki-latex")
        s.set("src", "data:text/plain;charset=utf-8,%s" % obj.caption)
        r = mathml.latex2mathml(obj.caption)       
        if not r:
            #r = ET.Element("em")
            #r.set("class", "math.error")
            #r.text = obj.caption
            pass
        s.append(r)
        return s


    # Links ---------------------------------------------------------

    def xwriteURL(self, obj):
        a = ET.Element("a", href=obj.caption)
        a.set("class", "mwx.link.external")
        if not obj.children:
            a.text = obj.caption
        return a

    def xwriteNamedURL(self, obj):
        a = ET.Element("a", href=obj.caption)
        a.set("class", "mwx.link.external")
        if not obj.children:
            name = "[%s]" % self.namedLinkCount
            self.namedLinkCount += 1
            a.text = name
        return a


    def xwriteSpecialLink(self, obj): # whats that?
        a = ET.Element("a", href=obj.target)
        a.set("class", "mwx.link.special")
        if not obj.children:
            a.text = obj.target
        return a

    def xwriteCategoryLink(self, obj):
        if not obj.colon and not obj.children:
            a = ET.Element("a", href=obj.target)
            a.set("class", "mwx.link.category")
            a.text = obj.target
            return a


    def xwriteLangLink(self, obj): # FIXME no valid url (but uri)
        if obj.target is None:
            return
        a = ET.Element("a", href=obj.target)
        a.set("class", "mwx.link.interwiki")
        if not obj.children:
            a.text = obj.target
        return a

       
    def xwriteImageLink(self, obj): 
        if obj.caption or obj.align:
            assert not obj.isInline() and not obj.thumb
            e = ET.Element("div")
            e.set("class", "mwx.image.float")
            if obj.align:
                e.set("align", obj.align)
            if obj.caption:
                e.text = obj.caption            
        else:
            e = ET.Element("span")
            if obj.isInline():
                e.set("class", "mwx.image.inline")
            if obj.thumb:
                e.set("class", "mwx.image.thumb")

        href ="Image:" + obj.target 
        e = ET.SubElement(e, "a", href=href)
        e.set("class", "mwx.link.image")

        # use a resolver which redirects to the real image
        # e.g. "http://anyhost/redir?img=IMAGENAME"
        if self.imagesrcresolver:
            imgsrc = self.imagesrcresolver.replace("IMAGENAME", obj.target)
        else:
            imgsrc = obj.target

        img = ET.SubElement(e, "img", src=imgsrc, alt="") 
        if obj.width:
            img.set("width", unicode(obj.width))
        if obj.height:
            img.set("height", unicode(obj.height))

        return e 

    def writeImageMap(self, obj): # FIXME!
        if obj.imagemap.imagelink:
            return self.write(t.imagemap.imagelink)


    def xwriteGallery(self, obj):
        s = ET.Element("div")
        s.set("class", "mwx.gallery")
        self.setVList(s, obj)
        return s

    
    # ---------- Generic XHTML Elements --------------------------------

    def xwriteGenericElement(self, t):
        if not hasattr(t, "starttext"):
            if hasattr(t, "_tag"):
                e = ET.Element(t._tag)
                self.setVList(e, t)
                return e
            else:
                log("skipping %r"%t)
                return
        else: 
            # parse html and return ET elements
            stuff = t.starttext + t.endtext
            try:
                if not t.endtext and not "/" in t.starttext:
                    stuff = t.starttext[:-1] + "/>"
                p =  ET.fromstring(stuff)
            except Exception, e:
                log("failed to parse %r \n" % t)
                parser.show(sys.stdout, t)
                #raise e
                p = None
        return p

    xwriteEmphasized = xwriteGenericElement
    xwriteStrong = xwriteGenericElement
    xwriteSmall = xwriteGenericElement
    xwriteBig = xwriteGenericElement
    xwriteCite = xwriteGenericElement
    xwriteSub = xwriteGenericElement
    xwriteSup = xwriteGenericElement
    xwriteCode = xwriteGenericElement
    xwriteBreakingReturn = xwriteGenericElement
    xwriteHorizontalRule = xwriteGenericElement
    xwriteTeletyped = xwriteGenericElement
    xwriteDiv = xwriteGenericElement
    xwriteSpan = xwriteGenericElement
    xwriteVar= xwriteGenericElement
    xwriteRuby = xwriteGenericElement
    xwriteRubyBase = xwriteGenericElement
    xwriteRubyParentheses = xwriteGenericElement
    xwriteRubyText = xwriteGenericElement
    xwriteDeleted = xwriteGenericElement
    xwriteInserted = xwriteGenericElement
    xwriteTableCaption = xwriteGenericElement
    xwriteDefinitionList = xwriteGenericElement
    xwriteDefinitionTerm = xwriteGenericElement
    xwriteDefinitionDescription = xwriteGenericElement

    def xwritePreFormatted(self, n):
        return ET.Element("pre")

    def xwriteParagraph(self, obj):
        """
        currently the parser encapsulates almost anything into paragraphs, 
        but XHTML1.0 allows no block elements in paragraphs.
        therefore we use the html-div-element. 

        this is a hack to let created documents pass the validation test.
        """
        e = ET.Element("div")
        e.set("class", "mwx.paragraph")
        return e


    # others: Index, Gallery, ImageMap  FIXME
    # see http://meta.wikimedia.org/wiki/Help:HTML_in_wikitext

    # ------- TAG nodes (deprecated) ----------------

    def xwriteOverline(self, s):
        e = ET.Element("span")
        e.set("class", "mwx.style.overline")
        return e    

    def xwriteUnderline(self, s):
        e = ET.Element("span")
        e.set("class", "mwx.style.underline")
        return e

    def xwriteSource(self, s):       
        # do we have a lang attribute here?
        e = ET.Element("code")
        e.set("class", "mwx.source")
        return e
    
    def xwriteCenter(self, s):
        e = ET.Element("span")
        e.set("class", "mwx.style.center")
        return e

    def xwriteStrike(self, s):
        e = ET.Element("span")
        e.set("class", "mwx.style.strike")
        return e

    def _xwriteBlockquote(self, s, klass): 
        e = ET.Element("blockquote")
        e.set("class", klass)
        for i in range(len(s.caption)-1):
            e = ET.SubElement(e, "blockquote")
            e.set("class", klass)
        return e
    
    def xwriteBlockquote(self, s):
        "margin to the left & right"
        self._xwriteBlockquote(s, klass="mwx.blockquote")

    def xwriteIndented(self, s):
        "margin to the left"
        self._xwriteBlockquote(s, klass="mwx.indented")

    def xwriteItem(self, item):
        return ET.Element("li")

    def xwriteItemList(self, lst):
        if lst.numbered:
            tag = "ol"
        else:
            tag = "ul"
        return ET.Element(tag)


def fixtree(element, parent=None):
    """
    the parser uses paragraphs to group anything
    this is not compatible with xhtml where nesting of 
    block elements is not allowed.
    """
    #blockelements = set("p","pre", "ul", "ol","blockquote", "hr", "dl")
    # TODO POSTPROCESS 
    
    # move section children after the section
    if isinstance(element, advtree.Section):
        last = element
        for c in element.children[1:]:
            c.moveto(last)
            last = c
        element.children = element.children[0:1] # contains the caption
    else:
        for c in element:
            fixtree(c, element)

def fixParagraphs(element):
    if isinstance(element, advtree.Paragraph) and isinstance(element.previous, advtree.Section) \
            and element.previous is not element.parent:
        element.moveto(element.previous.getLastChild())
        return True # changed
    else:
        changes = True
        while changes:
            changes = False
            for c in element.children[:]:
                changes = fixParagraphs(c)
                if changes:
                    break
        return False
    

def _fixBlockElements(element):
    """
    the parser uses paragraphs to group anything
    this is not compatible with xhtml where nesting of 
    block elements is not allowed.
    """
    blockelements = (advtree.Paragraph, advtree.PreFormatted, advtree.ItemList,
                        advtree.Blockquote, advtree.DefinitionList, advtree.HorizontalRule)

    if isinstance(element, blockelements) and element.parent and isinstance(element.parent, blockelements) and element.parent.parent:
        # s[ p, p[il[], text], p] -> s[p, p, il, p[text], p]
        # split element parents
        pstart = element.parent.copy()
        pend = element.parent.copy()
        for i,c in enumerate(pstart.children):
            if c is element:
                break
        pstart.children = pstart.children[:i]
        pend.children = pend.children[i+1:]
        print "action",  [pstart, element, pend]
        element.parent.parent.replaceChild(element.parent, [pstart, element, pend])
        return True # changed
    else:
        for c in element.children[:]:
            changes = fixBlockElements(c)
            if changes:
                return True
        return False
        
def fixBlockElements(root):
    while _fixBlockElements(root):
        print "_run fix block elements"


def main():
    for fn in sys.argv[1:]:
        r = advtree.getAdvTree(fn)
        fixParagraphs(r)
        fixBlockElements(r)
        parser.show(sys.stdout, r)
        odf = ODFWriter()
        odf.write(r)
        doc = odf.getDoc()

        import StringIO
        doc.toXml("%s.odf.xml"%fn)
        doc.save("%s.odf" % fn, True)
 
if __name__=="__main__":
    main()
