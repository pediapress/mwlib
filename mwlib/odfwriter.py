#! /usr/bin/env python

# Copyright (c) 2008-2009, PediaPress GmbH
# See README.rst for additional licensing information.
"""
TODO:
 * add license handling
 * implement missing methods: Imagemap, Hiero, Timeline, Gallery

More Info:
* http://books.evc-cit.info/odbook/book.html
* http://opendocumentfellowship.com/projects/odfpy
* http://testsuite.opendocumentfellowship.com/ sample documents
"""

from __future__ import division

import sys
import odf

from odf.opendocument import OpenDocumentText
from odf import text, dc, meta, table, draw, math, element
from mwlib.log import Log
from mwlib import advtree, writerbase, odfconf, parser
from mwlib import odfstyles as style
from mwlib.treecleaner import TreeCleaner

log = Log("odfwriter")

# check for ODF version
e = element.Element(qname = ("a","n"))
assert hasattr(e, "appendChild")
assert hasattr(e, "lastChild")
assert hasattr(e, "setAttribute")
del e

def showNode(obj):
    attrs = obj.__dict__.keys()
    log(obj.__class__.__name__ )
    stuff =  ["%s => %r" %(k,getattr(obj,k)) for k in attrs if
              (not k == "children") and getattr(obj,k)
              ]
    if stuff:
        log(repr(stuff))

class SkipChildren(object):
    "if returned by the writer no children are processed"
    def __init__(self, element=None):
        self.element = element


class ParagraphProxy(text.Element):
    """
    special handling since most problems occure arround paragraphs
    this is broken!
    """

    qname = (text.TEXTNS, 'p')
    def addElement(self, e):
        assert not hasattr(self, "writeto")
        assert e.parentNode is None
        assert e is not self

        if isinstance(e, ParagraphProxy):
            assert self.parentNode is not None
            #log("relinking paragraph %s" % e.type)
            self.parentNode.addElement(e) # add at the same level
            np = ParagraphProxy() # add copy at the same level
            np.attributes = self.attributes.copy()
            self.parentNode.addElement(np)
            self.writeto = np

        elif e.qname not in self.allowed_children:
            assert self.parentNode is not None
            #log("addElement", e.type, "not allowed in ", self.type)
            # find a parent that accepts this type
            p = self
            #print self, "looking for parent to accept", e
            while p.parentNode is not None and e.qname not in p.allowed_children:
                #print "p:", p
                assert p.parentNode is not p
                p = p.parentNode
            if e.qname not in p.allowed_children:
                assert p.parentNode is None
                log("ParagraphProxy:addElement() ", e.type, "not allowed in any parents, failed, should have been added to", self.type)
                return
            assert p is not self
            #log("addElement: moving", e.type, "to ", p.type)
            # add this type to the parent
            p.addElement(e)
            # add a new paragraph to this parent and link my addElement and addText to this
            np = ParagraphProxy()
            np.attributes = self.attributes
            p.addElement(np)
            self.writeto = np
        else:
            text.Element.addElement(self, e)

"""
we generate odf.text.Elements and
patch them with two specialities:
1) Element.writeto
2) ParagraphProxy(text.Element)
"""



class ODFWriter(object):
    ignoreUnknownNodes = True
    namedLinkCount = 1

    def __init__(self, env=None, status_callback=None, language="en", namespace="en.wikipedia.org", creator="", license="GFDL"):
        self.env = env
        self.status_callback = status_callback
        self.language = language
        self.namespace = namespace
        self.references = []
        self.doc =  OpenDocumentText()
        style.applyStylesToDoc(self.doc)
        self.text = self.doc.text
        self.namedLinkCount = 0
        self.conf = odfconf.OdfConf

        if creator:
            self.doc.meta.addElement(meta.InitialCreator(text=creator))
            self.doc.meta.addElement(dc.Creator(text=creator))
        if language is not None:
            self.doc.meta.addElement(dc.Language(text=language))
        if license is not None:
            self.doc.meta.addElement(meta.UserDefined(name="Rights", text=license))


    def writeTest(self, root):
        self.write(root, self.doc.text)

    def writeBook(self, book, output, removedArticlesFile=None, coverimage=None):
        """
        bookParseTree must be advtree and sent through preprocess()
        """

        if self.env and self.env.metabook:
            self.doc.meta.addElement(dc.Title(text=self.env.metabook.get("title", "")))
        #licenseArticle = self.env.metabook['source'].get('defaultarticlelicense','') # FIXME

        for e in book.children:
            self.write(e, self.doc.text)
        doc = self.getDoc()
        #doc.toXml("%s.odf.xml"%fn)
        doc.save(output, addsuffix=False)
        log( "writing to %r" % output )

    def getDoc(self, debuginfo=""):
        return self.doc

    def asstring(self, element = None):

        class Writer(object):
            def __init__(self):
                self.res = []
            def write(self, txt):
                if isinstance(txt, unicode):
                    self.res.append(str(txt))
                else:
                    self.res.append(txt)
            def getvalue(self):
                return "".join(self.res)

        s = Writer()
        if not element:
            element = self.doc.text
        element.toXml(0, s)

        return s.getvalue()

    def writeText(self, obj, parent):
        try:
            parent.addText(obj.caption)
        except odf.element.IllegalText:
            p = ParagraphProxy(stylename=style.textbody)
            try:
                parent.addElement(p)
                p.addText(obj.caption)
            except odf.element.IllegalChild:
                log("writeText:", obj, "not allowed in ", parent.type, "adding Paragraph failed")

    def write(self, obj, parent=None):
        assert parent is not None

        def saveAddChild(p,c):
            try:
                p.addElement(c)
                #print "save add child %r to %r" % (c, p)
                assert c.parentNode is not None # this check fails if the child could not be added
                return True
            except odf.element.IllegalChild:
                # fails if paragraph in span:  odfwriter >> write: u'text:p' 'not allowed in ' u'text:span' ', dumping'
                try: # maybe c has no attribute type
                    art = obj.getParentNodesByClass(advtree.Article)[0]
                    log("in article ", art.caption)
                    log("write:", c.type, "not allowed in ", p.type, ", dumping")
                except AttributeError:
                    log("missing .type attribute %r %r " %(c, p))
                return False


        while hasattr(parent, "writeto"):
            parent = parent.writeto # SPECIAL HANDLING

        # if its text, append to last node
        if isinstance(obj, parser.Text):
            self.writeText(obj, parent)
        else:
            # check for method
            m = "owrite" + obj.__class__.__name__
            m=getattr(self, m, None)

            if m: # find handler
                e = m(obj)

            elif self.ignoreUnknownNodes:
                log("Handler for node %s not found! SKIPPED" %obj.__class__.__name__)
                showNode(obj)
                e = None
            else:
                raise Exception("unknown node:%r" % obj)

            if isinstance(e, SkipChildren): # do not process children of this node
                if e.element is not None:
                    saveAddChild(parent, e.element)
                return # skip
            elif e is None:
                e = parent
            else:
                if not saveAddChild(parent, e):
                    return #

            for c in obj.children[:]:
                self.write(c,e)


    def writeChildren(self, obj, parent): # use this to avoid bugs!
        "writes only the children of a node"
        for c in obj:
            self.write(c, parent)


    def owriteArticle(self, a):
        self.references = [] # collect references
        title = a.caption
        log(u"processing article %s" % title)
        r = text.Section(stylename=style.sect, name=title) #, display="none")
        r.addElement(text.H(outlinelevel=1, stylename=style.ArticleHeader, text=title))
        return r

    def owriteChapter(self, obj):
        title = obj.caption
        item = text.Section(stylename=style.sect, name=title)
        item.addElement(text.H(outlinelevel=1, text=title, stylename=style.chapter))
        return item

    def owriteSection(self, obj):
        hXstyles = (style.h0,style.h1,style.h2,style.h3,style.h4,style.h5)

        # skip empty sections (as for eg References)
        hasDisplayContent = u"".join(x.getAllDisplayText().strip() for x in obj.children [1:]) \
            or obj.getChildNodesByClass(advtree.ImageLink) # FIXME, add AdvancedNode.hasContent property
        enabled = False
        if enabled and not hasDisplayContent:  # FIXME
            return SkipChildren()

        title = obj.children[0].getAllDisplayText()

        # = is level 0 as in article title =
        # == is level 1 as in mediawiki top level section ==
        # getSectionLevel() == 1 for most outer section level
        level = 1 + obj.getSectionLevel() # min: 1+0 = 1
        level = min(level, len(hXstyles))
        hX = hXstyles[level-1]

        r = text.Section(stylename=style.sect, name=title)
        r.addElement(text.H(outlinelevel=level, stylename=hX, text=title))
        obj.children = obj.children[1:]
        return r

    def owriteParagraph(self, obj):
        if obj.children:
            imgAsOnlyChild = bool(len(obj.children) == 1 and isinstance(obj.getFirstChild(), advtree.ImageLink))
            # handle special case nothing but an image in a paragraph
            if imgAsOnlyChild and isinstance(obj.next, advtree.Paragraph):
                img = obj.getFirstChild()
                img.moveto(obj.next.getFirstChild(), prefix=True)
                return SkipChildren()
            return ParagraphProxy(stylename=style.textbody)

    def owriteItem(self, item):
        li =text.ListItem()
        p = ParagraphProxy(stylename=style.textbody)
        li.addElement(p)
        li.writeto = p
        return li

    def owriteItemList(self, lst):
        if lst.numbered:
            return text.List(stylename=style.numberedlist)
        else:
            return text.List(stylename=style.unorderedlist)

    def owriteDefinitionList(self, obj):
        return text.List(stylename=style.definitionlist)

    def owriteDefinitionTerm(self, obj):
        li =text.ListItem()
        p = ParagraphProxy(stylename=style.definitionterm)
        li.addElement(p)
        li.writeto = p
        return li

    def owriteDefinitionDescription(self, obj):
        li = text.ListItem()
        p = ParagraphProxy(stylename=style.indentedSingle)
        li.addElement(p)
        li.writeto = p
        # FIXME, this should be handled in advtree!
        if not isinstance(obj.parent, advtree.DefinitionList):
            dl = text.List(stylename=style.definitionlist)
            dl.addElement(li)
            dl.writeto = p
            return dl

        return li


    def owriteBreakingReturn(self, obj):
        return text.LineBreak()

    def owriteCell(self, cell):
        t =  table.TableCell()
        p = ParagraphProxy(stylename=style.textbody)
        t.addElement(p)
        t.writeto = p
        # handle rowspan FIXME
        #
        #rs = cell.rowspan
        #if rs:
        #    t.setAttribute(":numberrowsspanned",str(rs))
        return t

    def owriteRow(self, row): # COLSPAN FIXME
        tr = table.TableRow()
        for c in row.children:
            cs =  c.colspan
            self.write(c,tr)
            if cs:
                tr.lastChild.setAttribute("numbercolumnsspanned",str(cs))
                for i in range(cs):
                    tr.addElement(table.CoveredTableCell())
        return SkipChildren(tr)

    def owriteCaption(self, obj):
        # are there caption not in tables ???? FIXME
        if isinstance(obj.parent, advtree.Table):
            return SkipChildren()
        pass # FIXME

    def owriteTable(self, obj): # FIXME ADD FORMATTING
        # http://books.evc-cit.info/odbook/ch04.html#text-table-section

        t = table.Table()
        tc = table.TableColumn(stylename=style.dumbcolumn,
                               numbercolumnsrepeated=str(obj.numcols)) # FIXME FIXME
        t.addElement(tc)

        captions = [c for c in obj.children if isinstance(c, advtree.Caption)]
        if not captions : # handle table w/o caption:
            return t
        else: # a section groups table-caption & table:
            if not len(captions) == 1:
                log("owriteTable: more than one Table Caption not handeled. Using only first Caption!")
            # group using a section
            sec = text.Section(stylename=style.sectTable, name="table section")
            p =  ParagraphProxy(stylename=style.tableCaption)
            sec.addElement(p)
            self.writeChildren(captions[0], p)# only one caption expected and allowed
            sec.addElement(t)
            sec.writeto=t
            return sec


# ---- inline formattings -------------------
# use span

    def owriteEmphasized(self, obj):
        return text.Span(stylename=style.emphasis)

    def owriteStrong(self, obj):
        return text.Span(stylename=style.strong)

    def owriteBold(self, obj):
        return text.Span(stylename=style.bold)

    def owriteItalic(self, obj):
        return text.Span(stylename=style.italic)

    def owriteSmall(self, obj):
        return text.Span(stylename=style.small)

    def owriteBig(self, obj):
        return text.Span(stylename=style.big)

    def owriteVar(self, obj):
        return text.Span(stylename=style.var)

    def owriteDeleted(self, obj):
        return text.Span(stylename=style.deleted)

    def owriteInserted(self, obj):
        return text.Span(stylename=style.inserted)

    def owriteRuby(self, obj):
        return text.Ruby()

    def owriteRubyText(self, obj):
        return text.RubyText()

    def owriteRubyBase(self, obj):
        return text.RubyBase()

    def owriteRubyParentheses(self, obj):
        pass # FIXME

    def owriteSub(self, obj):
        return text.Span(stylename=style.sub)

    def owriteSup(self, obj):
        return text.Span(stylename=style.sup)

    def owriteSpan(self, obj):
        return text.Span()

    def owriteOverline(self, s):
        return text.Span(stylename=style.overline)

    def owriteUnderline(self, s):
        return text.Span(stylename=style.underline)

    def owriteStrike(self, s):
        return text.Span(stylename=style.strike)

    def owriteTagNode(self, node):
        if getattr(node, 'caption', None) in ['hiero']:
            return SkipChildren()
        if getattr(node, 'caption', None) in ['abbr']:
            return self.owriteUnderline(node)


# ------- block formattings -------------------
# use paragraph

    def owriteCenter(self, s):
        return ParagraphProxy(stylename=style.center)

    def owriteCite(self, obj):
        return text.Span(stylename=style.cite)

    def owriteDiv(self, obj):
        return ParagraphProxy()

    def owriteTeletyped(self, obj):
        # (monospaced) or code, newlines ignored, spaces collapsed
        return text.Span(stylename=style.teletyped)

    def _replaceWhitespaces(self,obj, p):
        # replaces \n, \t and " " given from parser to ODF-valid tags
        # works on (styled) ParagraphProxy p
        rmap = {
            "\n":text.LineBreak,
            " ":text.S}
        col = []
        for c in obj.getAllDisplayText().replace("\t", " "*8).strip():
            if c in rmap:
                p.addText(u"".join(col))
                col = []
                p.addElement(rmap[c]())
            else:
                col.append(c)
        p.addText(u"".join(col)) # add remaining
        obj.children = []  # remove the children
        return p

    def owritePreFormatted(self, obj):
        p = ParagraphProxy(stylename=style.preformatted)
        return self._replaceWhitespaces(obj, p)

    def owriteSource(self, obj):
        p = ParagraphProxy(stylename=style.source)
        return self._replaceWhitespaces(obj, p)


    def owriteCode(self, obj):
        return text.Span(stylename=style.code)


    def owriteBlockquote(self, s):
        "margin to the left & right"
        indentlevel = len(s.caption)-1
        return ParagraphProxy(stylename=style.blockquote)


    def owriteIndented(self, s):
        "Writes a indented Paragraph. Margin to the left.\n Need a lenght of Indented.caption of 1,2 or 3."
        indentStyles = (style.indentedSingle, style.indentedDouble, style.indentedTriple)  # 0, 1, 2
        indentLevel = min(len(s.caption)-1, len(indentStyles)-1)
        return ParagraphProxy(stylename=indentStyles[indentLevel])


    def owriteMath(self, obj):
        """
        get a MATHML from Latex
        translate element tree to odf.Elements
        """
        #log("math")
        r = writerbase.renderMath(obj.caption, output_mode='mathml', render_engine='blahtexml')
        if not r:
            log("writerbase.renderMath failed!")
            return
        #print mathml.ET.tostring(r)

        def _withETElement(e, parent):
            # translate to odf.Elements
            for c in e.getchildren():
                n = math.Element(qname=(math.MATHNS, str(c.tag)))
                parent.addElement(n)
                if c.text:
                    text = c.text
                    #if not isinstance(text, unicode):  text = text.decode("utf8")
                    n.appendChild(odf.element.Text(text)) # n.addText(c.text)
                    # rffixme: odfpy0.8 errors:"AttributeError: Element instance has no attribute 'elements'" -> this is a lie!
                _withETElement(c, n)

        mathframe = draw.Frame(stylename=style.formula, zindex=0, anchortype="as-char")
        mathobject = draw.Object()
        mathframe.addElement(mathobject)
        mroot = math.Math()
        mathobject.addElement(mroot)
        _withETElement(r, mroot)
        return mathframe

    def owriteLink(self, obj):
        a = text.A(href= obj.url or "#")
        if not obj.children:
            a.addText(obj.target)
        return a

    owriteArticleLink = owriteLink
    obwriteLangLink = owriteLink
    owriteNamespaceLink = owriteLink
    owriteInterwikiLink = owriteLink
    owriteSpecialLink = owriteLink



    def owriteURL(self, obj):
        a = text.A(href=obj.caption)
        if not obj.children:
            a.addText(obj.caption)
        return a


    def owriteNamedURL(self, obj):
        # FIXME handle references
        a = text.A(href=obj.caption)
        if not obj.children:
            name = "[%s]" % self.namedLinkCount
            self.namedLinkCount += 1
            a.addText(name)
        return a


    def owriteSpecialLink(self, obj): # whats that?
        a = text.A(href=obj.target)
        if not obj.children:
            a.addText(obj.target)
        return a

    def owriteCategoryLink(self, obj):
        if True: # FIXME, collect and add to the end of the page
            return SkipChildren()
        if not obj.colon and not obj.children:
            a = text.A(href=obj.target)
            a.addText(obj.target)
            return a

    def owriteLangLink(self, obj):
        return SkipChildren() # dont want them

    def owriteReference(self, t):
        self.references.append(t)
        n =  text.Note(noteclass="footnote")
        nc = text.NoteCitation()
        n.addElement(nc )
        nc.addText(str(len(self.references)))
        nb = text.NoteBody()
        n.addElement( nb )
        p = ParagraphProxy(stylename=style.footnote)
        nb.addElement(p)
        n.writeto = p
        return n

    def owriteReferenceList(self, t):
        # already in odf footnotes
        pass

    def owriteImageMap(self, obj):
        pass # write children # fixme

    def owriteImageLink(self,obj,isImageMap=False):
        # see http://books.evc-cit.info/odbook/ch04.html
        # see rl.writer for more advanced image integration, including inline, floating, etc.
        # http://code.pediapress.com/hg/mwlib.rl rlwriter.py

        from PIL import Image as PilImage

        def sizeImage(w,h):

            """ calculate the target image size in inch.
            @param: (w,h): w(idth), h(eight) of image in px
            @type int
            @return: (w,h): w(idth), h(eight) of target image in inch (!)
            @rtype float"""


            if obj.isInline:
                scale = 1 / self.conf.paper['IMG_DPI_STANDARD']
            else:
                scale = 1 / self.conf.paper['IMG_DPI_INLINE']

            wTarget = scale * w # wTarget is in inch now
            hTarget = scale * h # hTarget is in inch now

            ##2do: obey the value of thumpnail
            if wTarget > self.conf.paper['IMG_MAX_WIDTH'] or hTarget > self.conf.paper['IMG_MAX_HEIGHT']:
                # image still to large, re-resize to max possible:
                scale = min(self.conf.paper['IMG_MAX_WIDTH']/w, self.conf.paper['IMG_MAX_HEIGHT']/h)

                return (w*scale, h*scale, scale)
            else:
                return (wTarget, hTarget, scale)

        if obj.colon == True:
            return # writes children
            #fixme: handle isImageMap

        if not self.env or not self.env.images:
            return
            #fixme: handle isImageMap

        imgPath = self.env.images.getDiskPath(obj.target)#, size=targetWidth) ????
        if not imgPath:
            log.warning('invalid image url')
            return
        imgPath = imgPath.encode('utf-8')

        (wObj,hObj) = (obj.width or 0, obj.height or 0)
        # sometimes the parser delivers only one value, w or h, so set the other = 0

        try:
            img = PilImage.open(imgPath)
            if img.info.get('interlace',0) == 1:
                log.warning("got interlaced PNG which can't be handeled by PIL")
                return
        except IOError:
            log.warning('img can not be opened by PIL')
            return

        (wImg,hImg) = img.size

        if wImg == 0 or wImg == 0:
            return

        # sometimes the parser delivers only one value, w or h, so set the other "by hand"
        aspectRatio = wImg/hImg

        if wObj>0 and not hObj>0:
            hObj = wObj / aspectRatio
        elif hObj>0 and not wObj>0:
            wObj = aspectRatio / hObj
        elif wObj==0 and hObj==0:
            wObj, hObj = wImg, hImg
        #hint: wObj/hObj are the values of the Thumbnail
        #      wImg/hImg are the real values of the image

        (width, height, scale) = sizeImage( wObj, hObj)


        widthIn = "%.2fin" % (width)
        heightIn= "%.2fin" % (height)

        innerframe = draw.Frame(stylename=style.frmInner, width=widthIn, height=heightIn)

        if isImageMap:
            innerframe.wImg = wImg
            innerframe.hImg = hImg
            innerframe.rescaleFactor = scale # needed cuz image map coordinates needs the same rescaled
            log ("wObj ,wImg: %s,%s" %(wObj,wImg))

        href = self.doc.addPicture(imgPath)
        innerframe.addElement(draw.Image(href=href))

        if obj.isInline():
                return SkipChildren(innerframe) # FIXME something else formatting?
        else:
            innerframe.setAttribute( "anchortype", "paragraph")


        widthIn = "%.2fin" % (width + style.frmOuter.internSpacing)
        heightIn= "%.2fin" % (height)

        # set image alignment
        attrs = dict(width=widthIn, anchortype="paragraph")
        floats = dict(right  = style.frmOuterRight,
                      center = style.frmOuterCenter,
                      left   = style.frmOuterLeft)
        attrs["stylename"] = floats.get(obj.align, style.frmOuterLeft)
        stylename=style.frmOuterLeft,
        frame = draw.Frame(**attrs)

        tb = draw.TextBox()
        frame.addElement(tb)
        p = ParagraphProxy(stylename=style.imgCaption)
        tb.addElement(p)
        p.addElement(innerframe)
        frame.writeto = p
        if isImageMap:
            frame.writeImageMapTo = innerframe
        return frame

    def owriteFont(self, n):
        pass # simply write children

    def owriteNode(self, n):
        pass # simply write children

    def owriteGallery(self, obj):
        pass # simply write children FIXME

    def owriteHorizontalRule(self, obj):
        p = ParagraphProxy(stylename=style.hr)
        return p


# UNIMPLEMENTED  -----------------------------------------------

    def writeTimeline(self, obj):
        data = obj.caption
        pass # FIXME

    def writeHiero(self, obj): # FIXME parser support
        data = obj.caption
        pass # FIXME



# - func  ---------------------------------------------------


def writer(env, output, status_callback):
    if status_callback:
        buildbook_status = status_callback.getSubRange(0, 50)
    else:
        buildbook_status = None
    book = writerbase.build_book(env, status_callback=buildbook_status)
    scb = lambda status, progress :  status_callback is not None and status_callback(status=status, progress=progress)
    scb(status='preprocessing', progress=50)
    preprocess(book)
    scb(status='rendering', progress=60)
    w = ODFWriter(env, status_callback=scb)
    w.writeBook(book, output=output)

writer.description = 'OpenDocument Text'
writer.content_type = 'application/vnd.oasis.opendocument.text'
writer.file_extension = 'odt'


# - helper funcs   r ---------------------------------------------------

def preprocess(root):
    #advtree.buildAdvancedTree(root)
    #xmltreecleaner.removeChildlessNodes(root)
    #xmltreecleaner.fixLists(root)
    #xmltreecleaner.fixParagraphs(root)
    #xmltreecleaner.fixBlockElements(root)
    #print"*** parser raw "*5
    #parser.show(sys.stdout, root)
    #print"*** new TreeCleaner "*5
    advtree.buildAdvancedTree(root)
    tc = TreeCleaner(root)
    tc.cleanAll()
    #parser.show(sys.stdout, root)

# ==============================================================================

def main():
    for fn in sys.argv[1:]:

        from mwlib.dummydb import DummyDB
        from mwlib.uparser import parseString
        db = DummyDB()
        input = unicode(open(fn).read(), 'utf8')
        r = parseString(title=fn, raw=input, wikidb=db)
        #parser.show(sys.stdout, r)
        #advtree.buildAdvancedTree(r)
        #tc = TreeCleaner(r)
        #tc.cleanAll()


        preprocess(r)
        parser.show(sys.stdout, r)
        odf = ODFWriter()
        odf.writeTest(r)
        doc = odf.getDoc()
        #doc.toXml("%s.xml"%fn)
        doc.save(fn, True)


if __name__=="__main__":
    main()
