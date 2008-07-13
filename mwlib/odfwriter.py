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
 * fix license handling
 * implement missing methods
 * add missing styles
 * use ODF supported special features for
  * references
  * TableOfContents


More Info:
* http://books.evc-cit.info/odbook/book.html
* http://opendocumentfellowship.com/projects/odfpy
* http://testsuite.opendocumentfellowship.com/ sample documents
"""

from __future__ import division
import sys
try:
    import odf
except ImportError, e:
    print "you need to install odfpy: http://opendocumentfellowship.com/projects/odfpy"
    raise

from odf.opendocument import OpenDocumentText
from odf import text, dc, meta, table, draw, math
from mwlib import parser
from mwlib import mathml
from mwlib.log import Log
from mwlib import advtree 
from mwlib import odfstyles as style
from mwlib import xmltreecleaner
from mwlib import writerbase

log = Log("odfwriter")

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
    """

    qname = (text.TEXTNS, 'p')
    def addElement(self, e):
        assert self.parentNode is not None
        if isinstance(e, ParagraphProxy):
            self.addElement(text.LineBreak())
            e.addElement = self.addElement
            e.addText = self.addText
            e.parentNode = self.parentNode
        elif e.qname not in self.allowed_children:
            "this is currently broken, since it does not add stuff in the correct order" # FIXME
            #log("addElement", e.type, "not allowed in ", self.type)
            # find a parent that accepts this type
            p = self
            while p.parentNode is not None and e.qname not in p.allowed_children:
                p = p.parentNode
            if e.qname not in p.allowed_children:
                assert p.parentNode is None
                log("addElement:", e.type, "not allowed in any parents, failed, was added to", self.type)
                return

            # add this type to the parent
            p.addElement(e)
            # add a new paragraph to this parent and link my addElement and addText to this
            np = ParagraphProxy()
            p.addElement(np) # THIS MAY FAIL
            self.addElement = np.addElement
            self.addText = np.addText
        else:
            text.Element.addElement(self, e)

"""
we generate odf.text.Elements and
patch them with two specialities:
2) sometimes we add a "writeto" attribute to a  (child) element
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

        if creator:
            self.doc.meta.addElement(meta.InitialCreator(text=creator))
            self.doc.meta.addElement(dc.Creator(text=creator))
        if language is not None:
            self.doc.meta.addElement(dc.Language(text=language))
        if license is not None:
            self.doc.meta.addElement(meta.UserDefined(name="Rights", text=license))


    def writeBook(self, book, output, removedArticlesFile=None, coverimage=None):
        """
        bookParseTree must be advtree and sent through preprocess()
        """
        
        self.doc.meta.addElement(dc.Title(text=u"collection title fixme"))
        #self.baseUrl = book.source['url']
        #self.wikiTitle = book.source.get('name')
        # add chapters FIXME
        for e in book.children:
            r = self.write(e, self.doc.text)
        #licenseArticle = self.env.metabook['source'].get('defaultarticlelicense','') # FIXME
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

        #import StringIO
        #s = StringIO.StringIO()
        s = Writer()
        if not element:
            element = self.doc.text 
        element.toXml(0, s)
       
        return s.getvalue()
        #return unicode(s.buf) + ''.join(s.buflist)

    
    def writeText(self, obj, parent):
        try:
            parent.addText(obj.caption)
        except odf.element.IllegalText:
            # try to wrap it into a paragraph
            p = ParagraphProxy(stylename=style.textbody)
            try:
                parent.addElement(p)
                p.addText(obj.caption)
            except odf.element.IllegalChild:
                log("writeText:", obj, "not allowed in ", parent.type, "adding Paragraph failed")


    def write(self, obj, parent=None):
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
                log("SKIPPED")
                showNode(obj)
                e = None
            else:
                raise Exception("unknown node:%r" % obj)
            
            if isinstance(e, SkipChildren): # do not process children of this node
                return e.element
            elif e is None:
                e = parent

            # FIXME, this for addElement in ParagraphProxy
            e.parentNode = parent # since parent must not be None, but this is broken

            p = e
            if hasattr(e, "writeto"):
                p = e.writeto # SPECIAL HANDLING 

            for c in obj.children[:]:
                ce = self.write(c,p)
                if ce is not None and ce is not p:                    
                    try: 
                        p.addElement(ce)
                    except odf.element.IllegalChild:
                        log( "write:", ce.type, "not allowed in ", p.type)

            return e

    def writeChildren(self, obj, parent): # use this to avoid bugs!
        "writes only the children of a node"
        if hasattr(parent, "writeto"):
            parent = parent.writeto
        for c in obj:                    
            res = self.write(c, parent)
            if res is not None and res is not parent:
                try: 
                    parent.addElement(res)
                except odf.element.IllegalChild:
                    log( "writeChildren:", res.type, "not allowed in ", parent.type)


    def owriteArticle(self, a):
        self.references = [] # collect references
        title = a.caption
        r = text.Section(stylename=style.sect, name=title) #, display="none")
        self.doc.text.addElement(r)
        r.addElement(text.H(outlinelevel=1, stylename=style.ArticleHeader, text=title))
        # write reference list writeReferences FIXME       
        return r # mhm 

    def owriteChapter(self, obj):
        pass # FIXME


    def owriteSection(self, obj):
        level = 1 + obj.getSectionLevel() # H1 is for an article, starting with h2
        #title = u"%d %s" %(level,  obj.children[0].children[0].caption ) # FIXME (debug output)
        title = obj.children[0].children[0].caption
        r = text.Section(stylename=style.sect, name=title) 
        hXstyle = (style.h1,style.h2,style.h3,style.h4,style.h5,style.h6)[level-1]
        r.addElement(text.H(outlinelevel=level, stylename=hXstyle, text=title))
        obj.children = obj.children[1:]
        return r

    def owriteParagraph(self, obj):
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

    def owriteDefinitionList(self, lst):
        return text.List(stylename=style.textbody)

    def owriteDefinitionTerm(self, obj):
        return self.owriteItem(obj)


    def owriteDefinitionDescription(self, obj):
        li = text.ListItem(stylename=style.unorderedlist) # fixme
        p = ParagraphProxy(stylename=style.indented)
        li.addElement(p)
        li.writeto = p
        return li


    def owriteBreakingReturn(self, obj):
        return text.LineBreak()

    def owriteCell(self, cell):
        t =  table.TableCell()
        p = ParagraphProxy(stylename=style.textbody)
        t.addElement(p)
        t.writeto = p
        return t    

    def owriteRow(self, row): # COLSPAN FIXME
        tr = table.TableRow()
        for c in row.children:
            cs =  c.vlist.get("colspan", 0)
            cell = self.write(c,tr)
            if cs:
                cell.addAttribute("numbercolumnsspanned",str(cs))
            tr.addElement(cell)
            for i in range(cs):
                tr.addElement(table.CoveredTableCell())
        return SkipChildren(tr)

    def owriteTable(self, obj): # FIXME ADD FORMATTING
        # http://books.evc-cit.info/odbook/ch04.html#text-table-section
        t = table.Table()
        tc = table.TableColumn(stylename=style.dumbcolumn, numbercolumnsrepeated=str(obj.numcols)) # FIXME FIXME
        t.addElement(tc)
        return t


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



# ------- block formattings -------------------
# use paragraph

    def owriteCenter(self, s):
        return ParagraphProxy(stylename=style.center)

    def owriteCite(self, obj): 
        return ParagraphProxy(stylename=style.cite)

    def owriteDiv(self, obj): 
        return ParagraphProxy()
        
    def owriteTeletyped(self, obj):
        # (monospaced) or code, newlines ignored, spaces collapsed
        return ParagraphProxy(stylename=style.teletyped)


    def owritePreFormatted(self, n):
        # need to replace \n \t
        frame = draw.Frame(stylename=style.graphic,anchortype="paragraph")
        tb = draw.TextBox()
        frame.addElement(tb)
        p = ParagraphProxy(stylename=style.preformatted) 
        tb.addElement(p)
        col = []
        for c in n.getAllDisplayText():
            if c == "\n":
                p.addText(u"".join(col))
                col = []
                p.addElement(text.LineBreak())
            elif c == "\t":
                p.addText(u"".join(col))
                col = []
                p.addElement(text.Tab())
            elif c == " ":
                p.addText(u"".join(col))
                col = []
                p.addElement(text.S()) 
            else:
                col.append(c)
        p.addText(u"".join(col))
        n.children = []  # remove the children
        return frame

    # FIXME
    owriteCode = owritePreFormatted
    owriteSource = owritePreFormatted

#    def owriteCode(self, obj): 
#        return ParagraphProxy(stylename=style.code)

#    def owriteSource(self, obj): 
#        return ParagraphProxy(stylename=style.source)

    
    def owriteBlockquote(self, s):
        "margin to the left & right"
        indentlevel = len(s.caption)-1
        return ParagraphProxy(stylename=style.blockquote)


    def owriteIndented(self, s):
        "margin to the left"
        indentlevel = len(s.caption)-1
        return ParagraphProxy(stylename=style.indented)

 
    def owriteMath(self, obj): 
        """
        get a MATHML from Latex
        translate element tree to odf.Elements
        """
        r = mathml.latex2mathml(obj.caption)     # returns an element tree parse tree
        #print mathml.ET.tostring(r)
        def _withETElement(e, parent):
            # translate to odf.Elements
            for c in e.getchildren():
                n = math.Element(qname=(math.MATHNS, str(c.tag)))
                parent.addElement(n)
                if c.text:
                    text = c.text
                    #print repr(text)
                    #if not isinstance(text, unicode):  text = text.decode("utf8")
                    n.elements.append(odf.element.Text(text)) # n.addText(c.text)
                _withETElement(c, n)

        mathframe = draw.Frame(stylename=style.formula, zindex=0, anchortype="as-char") 
#        mathframe.addAttribute("minwidth","2.972cm") # needed to add those attributes in order to see something
        # fo:min-width="0.7902in" 
        #mathframe.addAttribute("height","1.138cm")
        mathobject = draw.Object() 
        mathframe.addElement(mathobject)
        mroot = math.Math()
        mathobject.addElement(mroot)
        _withETElement(r, mroot)
        return mathframe


    def owriteLink(self, obj): 
        if self.env:
            url = self.env.get_source()["url"].rsplit("/",1)[0] + "/" + obj.target # FIXME
        else:
            url=obj.target
        a = text.A(href=url)
        if not obj.children:
            a.addText(obj.target)
        return a

    owriteArticleLink = owriteLink 
    obwriteLangLink = owriteLink # FIXME
    owriteNamespaceLink = owriteLink# FIXME
    owriteInterwikiLink = owriteLink# FIXME
    owriteSpecialLink = owriteLink# FIXME



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
            return
        if not obj.colon and not obj.children:
            a = text.A(href=obj.target)
            a.addText(obj.target)
            return a


    def owriteLangLink(self, obj):
        obj.children=[]
        pass # we dont want them in the PDF


    def owriteReference(self, t): 
        self.references.append(t)
        s =  text.Span(stylename=style.sup)
        s.addText(u"[%d]" %  len(self.references))
        return SkipChildren(s)


    def writeReferenceList(self, t):
        pass

    def owriteReferenceList(self, t):
        if not self.references:
            return
        ol =  text.List(stylename=style.numberedlist)
        for i,ref in enumerate(self.references):
            li = self.owriteItem(None)
            ol.addElement(li)
            self.writeChildren(ref, parent=li)
        self.references = []
        return SkipChildren(ol) # shall not have any children??
       

    def owriteImageMap(self, obj):
        pass # write children # fixme
    
    def owriteImageLink(self,obj):
        # see http://books.evc-cit.info/odbook/ch04.html
        # see rl.writer for more advanced image integration, including inline, floating, etc.
        # http://code.pediapress.com/hg/mwlib.rl rlwriter.py

        from PIL import Image as PilImage


        ######### IMAGE CONFIGURATION
        cm = 28.346456692913385
        max_img_width = 9 # max size in cm 
        max_img_height = 12 
        min_img_dpi = 75 # scaling factor in respect to the thumbnail-size in the wikimarkup which limits image-size
        inline_img_dpi = 100 # scaling factor for inline images. 100 dpi should be the ideal size in relation to 10pt text size 
        targetWidth = 800  # target image width 
        scale = 1./75

        def sizeImage(w,h):
            if obj.isInline():
                scale = 1 / (inline_img_dpi / 2.54)
            else:
                scale = 1 / (min_img_dpi / 2.54)
            _w = w * scale
            _h = h * scale
            if _w > max_img_width or _h > max_img_height:
                scale = min( max_img_width/w, max_img_height/h)
                return (w*scale*cm, h*scale*cm)
            else:
                return (_w*cm, _h*cm)



        if obj.colon == True:
            return # writes children


        if not self.env or not self.env.images:
            return

        imgPath = self.env.images.getDiskPath(obj.target, size=targetWidth)
        if not imgPath:
            log.warning('invalid image url')
            return
        imgPath = imgPath.encode('utf-8')
               

        (w,h) = (obj.width or 0, obj.height or 0)

        try:
            img = PilImage.open(imgPath)
            if img.info.get('interlace',0) == 1:
                log.warning("got interlaced PNG which can't be handeled by PIL")
                return
        except IOError:
            log.warning('img can not be opened by PIL')
            return
        (_w,_h) = img.size
        if _h == 0 or _w == 0:
            return
        aspectRatio = _w/_h                           

        if w>0 and not h>0:
            h = w / aspectRatio
        elif h>0 and not w>0:
            w = aspectRatio / h
        elif w==0 and h==0:
            w, h = _w, _h

        (width, height) = sizeImage( w, h)
        align = obj.align
            

        width = "%.2fin" % (width * scale)
        height = "%.2fin" % (height * scale)
        #frame = draw.Frame(stylename=style.graphic, width=width, height=height, x="1.5cm", y="2.5cm")
        innerframe = draw.Frame(stylename=style.graphic, width=width, height=height)
        href = self.doc.addPicture(imgPath)
        innerframe.addElement(draw.Image(href=href))


        if obj.isInline():
            return SkipChildren(innerframe) # FIXME something else formatting?
        else:
            innerframe.addAttribute( "anchortype", "paragraph")


        """
        <frame>
          <textbox>
           <p>
            <frame>
             <image>
            </frame>
           caption
        """

        frame = draw.Frame(stylename=style.graphic, width=width,anchortype="paragraph")
        tb = draw.TextBox()
        frame.addElement(tb)
        p = ParagraphProxy(stylename=style.textbody)
        tb.addElement(p)
        p.addElement(innerframe)
        frame.writeto = p
        return frame




    def owriteNode(self, n):
        pass # simply write children

    def owriteGallery(self, obj):
        pass # simply write children FIXME

    def owriteHorizontalRule(self, obj):
        p = ParagraphProxy(stylename=style.hr)
        return p


    def setVList(self, element, node): # FIXME N USEME
        """
        sets html attributes as found in the wikitext
        if this method is used it should be called *after* 
        the class attribute is set to some mwx.value.
        """
        if hasattr(node, "vlist") and node.vlist:
            #print "vlist", element, node
            saveclass = element.get("class")
            for k,v in self.xserializeVList(node.vlist):
                element.set(k,v)
            if saveclass and element.get("class") != saveclass:
                element.set("class", " ".join((saveclass, element.get("class"))))

    def xserializeVList(self,vlist): # FIXME N USEME
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





#  Special Objects -----------------------------------------------

    def xwriteTimeline(self, obj): 
        data = obj.caption
        pass # FIXME

    def xwriteHiero(self, obj): # FIXME parser support
        data = obj.caption
        pass # FIXME


    def writeImageMap(self, obj): # FIXME!
        if obj.imagemap.imagelink:
            return self.write(obj.imagemap.imagelink)
        



# - func  ---------------------------------------------------


def writer(env, output, status_callback):
    book = writerbase.build_book(env, status_callback=status_callback, progress_range=(10, 60))
    scb = lambda status, progress :  status_callback is not None and status_callback(status,progress)
    scb(status='preprocessing', progress=70)
    for c in book.children:
        preprocess(c)
    scb(status='rendering', progress=80)
    ODFWriter(env, status_callback=scb).writeBook(book, output=output)

writer.description = 'OpenDocument Text'
writer.content_type = 'application/vnd.oasis.opendocument.text'
writer.file_extension = 'odt'

    
# - helper funcs   r ---------------------------------------------------

def preprocess(root):
    advtree.buildAdvancedTree(root)
    # remove nav boxes
#    for c in root.getAllChildren():
#        if c.isNavBox() and c.parent is not None:
#            c.parent.removeChild(c)
    xmltreecleaner.removeChildlessNodes(root)
    xmltreecleaner.fixLists(root)
    xmltreecleaner.fixParagraphs(root)
    xmltreecleaner.fixBlockElements(root)





# ==============================================================================

def main():
    for fn in sys.argv[1:]:
        from mwlib.dummydb import DummyDB
        from mwlib.uparser import parseString
        db = DummyDB()
        input = unicode(open(fn).read(), 'utf8')
        r = parseString(title=fn, raw=input, wikidb=db)
        parser.show(sys.stdout, r)
        advtree.buildAdvancedTree(r)
        preprocess(r)
        parser.show(sys.stdout, r)
        odf = ODFWriter()
        odf.write(r)
        doc = odf.getDoc()
        doc.toXml("%s.xml"%fn)
        doc.save(fn, True)
 
if __name__=="__main__":
    main()
