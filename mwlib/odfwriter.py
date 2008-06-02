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
 * implement missing methods
 * add missing styles

More Info:
* http://books.evc-cit.info/odbook/book.html
* http://opendocumentfellowship.com/projects/odfpy
"""
import sys, exceptions
try:
    import odf
except exceptions.ImportError, e:
    print "you need to install odfpy: http://opendocumentfellowship.com/projects/odfpy"
    raise exceptions.ImportError, e

from odf.opendocument import OpenDocumentText
from odf import text, dc, meta, table, draw, math
from mwlib import parser,  mathml
from mwlib.log import Log
import advtree 
import odfstyles as style

log = Log("odfwriter")

def showNode(obj):
    attrs = obj.__dict__.keys()
    log(obj.__class__.__name__ ) 
    stuff =  ["%s => %r" %(k,getattr(obj,k)) for k in attrs if 
              (not k == "children") and getattr(obj,k)
              ]
    if stuff:
        log(repr(stuff))


class ODFWriter(object):
    namedLinkCount = 1

    def __init__(self, language="en", namespace="en.wikipedia.org", creator="", license="GFDL", images=None):
        self.language = language
        self.namespace = namespace
        self.images = images
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


    def writeBook(self, book, bookParseTree, output, removedArticlesFile=None, coverimage=None):
        outfile = output
        advtree.buildAdvancedTree(bookParseTree)
        preprocess(bookParseTree)
        self.book = book
        self.doc.meta.addElement(dc.Title(text=u"collection title fixme"))
        self.baseUrl = book.source['url']
        self.wikiTitle = book.source.get('name')
        for e in bookParseTree.children:
            r = self.write(e, self.doc.text)
        licenseArticle = self.book.source.get('defaultarticlelicense','')
        doc = self.getDoc()
        #doc.toXml("%s.odf.xml"%fn)
        doc.save(outfile, True)
        print "writing to", outfile
        
    def getDoc(self, debuginfo=""):
        return self.doc

    def asstring(self, element = None):
        import StringIO
        s = StringIO.StringIO()
        if not element:
            element = self.doc.text 
        element.toXml(0, s)
        s.seek(0)
        return s.read()
    
    def writeText(self, obj, parent):
        try:
            parent.addText(obj.caption)
        except odf.element.IllegalText:
            print "writeText:", obj, "not allowed in ", parent.type, "adding Paragraph"
            # try to wrap it into a paragraph
            p = text.P(stylename=style.textbody)
            try:
                parent.addElement(p)
                p.addText(obj.caption)
            except odf.element.IllegalChild:
                print  "...failed" # FAILS FOR FRAMES # FIXME!



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
                log("SKIPPED")
                showNode(obj)
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
                        print "write:", ce.type, "not allowed in ", e.type
                        #e.parentNode.addElement(ce)
                        
            return e


    def owriteArticle(self, a):
        #if a.caption:
        #    
        # FIXME
        self.references = [] # collect references
        title = a.caption
        r = text.Section(stylename=style.sect, name=title) #, display="none")
        self.doc.text.addElement(r)
        r.addElement(text.H(outlinelevel=1, stylename=style.ArticleHeader, text=title))
       
        #for c in a.children:
        #    self.write(c, r)
        #if self.references:
        #    # FIXME add header
        #    r.addElement( self.writeReferences(None))

        return r # mhm 

    def owriteSection(self, obj):
        level = 1 + obj.getLevel()
        #title = u"%d %s" %(level,  obj.children[0].children[0].caption ) # FIXME (debug output)
        title = obj.children[0].children[0].caption
        r = text.Section(stylename=style.sect, name=title) #, display="none")
        hXstyle = (style.h1,style.h2,style.h3,style.h4,style.h5,style.h6)[level-1]
        r.addElement(text.H(outlinelevel=level, stylename=hXstyle, text=title))
        obj.children = obj.children[1:]
        return r

    def owriteParagraph(self, obj):
        return text.P(stylename=style.textbody)
        
    def owriteItem(self, item):
        li =text.ListItem()
        p = text.P(stylename=style.textbody)
        li.addElement(p)
        
        def _addText(text):
            p.addText(text)

        def _addElement(e):
            p.addElement(e)

        li.addText = _addText
        li.addElement = _addElement
        
        return li

    def owriteItemList(self, lst):
        if lst.numbered:
            tag = "ol"
        else:
            tag = "ul"
        return text.List(stylename=style.textbody)

    def owriteBreakingReturn(self, obj):
        return text.LineBreak()



    def owriteCell(self, cell):
        #self.setVList(td, cell)           
        return table.TableCell()
            
    def owriteRow(self, row):
        return table.TableRow()

    def owriteTable(self, t):           
        #self.setVList(table, t)           
        #if t.caption:
        #    c = ET.SubElement(table, "caption")
        #    self.writeText(t.caption, c)
        return table.Table()

    def owriteEmphasized(self, obj):
        return text.Span(stylename=style.emphasis)

    def owriteStrong(self, obj):
        return text.Span(stylename=style.strong)

    def owriteBold(self, obj):
        return text.Span(stylename=style.bold)

    def owriteItalic(self, obj):
        return text.Span(stylename=style.italic)

    # Strong Small Big, Cite, Sub, Sup, Code, 

    def owriteChapter(self, obj):
        pass


    def owriteMath(self, obj): 
        """
        get a MATHML from Latex
        translate element tree to odf.Elements
        
        <draw:frame draw:style-name="fr1" draw:name="Objekt1" text:anchor-type="as-char" svg:width="2.972cm" svg:height="1.138cm" draw:z-index="0">
          <draw:object xlink:href="./MathML" xlink:type="simple" xlink:show="embed" xlink:actuate="onLoad"/>
        </draw:frame>

        """

        r = mathml.latex2mathml(obj.caption)     # returns an element tree parse tree
        #print mathml.ET.tostring(r)

        
        def _withETElement(e, parent):
            # translate to odf.Elements
            for c in e.getchildren():
                n = math.Element(qname=(math.MATHNS, c.tag))
                parent.addElement(n)
                if c.text:
                    n.elements.append(odf.element.Text(c.text)) # n.addText(c.text)
                _withETElement(c, n)




        mathframe = draw.Frame() 
        #mathframe.addAttribute("z-index","0")
        mathframe.addAttribute("width","2.972cm") # needed to add thos attributes in order to see something
        mathframe.addAttribute("height","1.138cm")


        mathobject = draw.Object() 
        mathframe.addElement(mathobject)
        mroot = math.Math()
        mathobject.addElement(mroot)
        _withETElement(r, mroot)
        

        return mathframe
        


    def owriteImageLink(self, obj):
        # see http://books.evc-cit.info/odbook/ch04.html
        print "in write imageLink"
        if not self.images:
            return

        targetWidth = 400
        imgPath = self.images.getDiskPath(obj.target, size=targetWidth)
        print imgPath
        if not imgPath:
            print "NO IMAGE PATH", obj, obj.target
            return
        imgPath = imgPath.encode('utf-8')
        print "have img here", imgPath
        frame = draw.Frame(stylename=style.photo, width="12cm", height="9cm", x="1.5cm", y="2.5cm")
        href = self.doc.addPicture(imgPath)
        frame.addElement(draw.Image(href=href))
        return frame




    def owriteLink(self, obj): 
        a = text.A(href=obj.target)
        if not obj.children:
            a.addText(obj.target)
        return a

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
        if not obj.colon and not obj.children:
            a = text.A(href=obj.target)
            a.addText(obj.target)
            return a


    def owriteLangLink(self, obj): # FIXME no valid url (but uri)
        if obj.target is None:
            return
        a = text.A(href=obj.target)
        if not obj.children:
            a.addText(obj.target)
        return a

    def owriteReference(self, t):
        self.references.append(t)
        s =  text.Span(stylename=style.superscript)
        s.addText(unicode( len(self.references)))
        return s

    def owriteReferenceList(self, t):
        if not self.references:
            return
        ol =  text.List(stylename=style.textbody)
        for i,r in enumerate(self.references):
            li = self.owriteItem(None)
            ol.addElement(li)
            for x in r:                    
                self.write(x, li) 
        self.references = []            
        return ol
       


    def writeImageLink(self,obj):  # INACTIVE COPY FROM RL WRITER TO LEARN HOW TO GET CORRECT SIZE
        if obj.colon == True:
            items = []
            for node in obj.children:
                items.extend(self.write(node))
            return items

        targetWidth = 400
        if self.imgDB:
            imgPath = self.imgDB.getDiskPath(obj.target, size=targetWidth)
            if imgPath:
                #self._cleanImage(imgPath)
                imgPath = imgPath.encode('utf-8')
                self.tmpImages.add(imgPath)
        else:
            imgPath = ''
        if not imgPath:
            log.warning('invalid image url')
            return []
               
        def sizeImage(w,h):
            max_img_width = 7 # max size in cm FIXME: make this configurable
            max_img_height = 11 # FIXME: make this configurable
            scale = 1/30 #. 100 dpi = 30 dpcm <-- this is the minimum pic resolution FIXME: make this configurable
            _w = w * scale
            _h = h * scale
            if _w > max_img_width or _h > max_img_height:
                scale = min( max_img_width/w, max_img_height/h)
                return (w*scale*cm, h*scale*cm)
            else:
                return (_w*cm, _h*cm)

        (w,h) = (obj.width or 0, obj.height or 0)

        try:
            from PIL import Image as PilImage
            img = PilImage.open(imgPath)
            if img.info.get('interlace',0) == 1:
                log.warning("got interlaced PNG which can't be handeled by PIL")
                return []
        except IOError:
            log.warning('img can not be opened by PIL')
            return []
        (_w,_h) = img.size
        if _h == 0 or _w == 0:
            return []
        aspectRatio = _w/_h                           
           
        if w>0 and not h>0:
            h = w / aspectRatio
        elif h>0 and not w>0:
            w = aspectRatio / h
        elif w==0 and h==0:
            w, h = _w, _h

        (width, height) = sizeImage( w, h)
        align = obj.align
            
        txt = []
        for node in obj.children:
            res = self.write(node)
            if isInline(res):
                txt.extend(res)
            else:
                log.warning('imageLink contained block element: %s' % type(res))
        if obj.isInline() : # or self.nestingLevel: 
            #log.info('got inline image:',  imgPath,"w:",width,"h:",height)
            txt = '<img src="%(src)s" width="%(width)fin" height="%(height)fin" valign="%(align)s"/>' % {
                'src':unicode(imgPath, 'utf-8'),
                'width':width/100,
                'height':height/100,
                'align':'bottom',
                }
            return txt
        # FIXME: make margins and padding configurable
        captionTxt = '<i>%s</i>' % ''.join(txt)  #filter
        #return [Figure(imgPath, captionTxt=captionTxt,  captionStyle=text_style('figure', in_table=self.nestingLevel), imgWidth=width, imgHeight=height, margin=(0.2*cm, 0.2*cm, 0.2*cm, 0.2*cm), padding=(0.2*cm, 0.2*cm, 0.2*cm, 0.2*cm), align=align)]

























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












# - helper funcs   r ---------------------------------------------------



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


def _fixParagraphs(element):
    if isinstance(element, advtree.Paragraph) and isinstance(element.previous, advtree.Section) \
            and element.previous is not element.parent:
        prev = element.previous
        parent = element.parent
        element.moveto(prev.getLastChild())
        assert element not in parent.children
        assert element in prev.children
        assert element.parent is prev
        return True # changed
    else:
        for c in element.children[:]:
            if _fixParagraphs(c):
                return True


def fixParagraphs(root):
    while _fixParagraphs(root):
        print "_run fix paragraphs"

    

def _fixBlockElements(element):
    """
    the parser uses paragraphs to group anything
    this is not compatible with xhtml where nesting of 
    block elements is not allowed.
    """
    blockelements = (advtree.Paragraph, advtree.PreFormatted, advtree.ItemList,advtree.Section, advtree.Table,
                     advtree.Blockquote, advtree.DefinitionList, advtree.HorizontalRule)

    if isinstance(element, blockelements) and element.parent and isinstance(element.parent, blockelements) \
            and not isinstance(element.parent, advtree.Section) : # Section is no problem if parent
        if not element.parent.parent:
            print "missing parent parent", element, element.parent, element.parent.parent
            assert element.parent.parent
        
        # s[ p, p[il[], text], p] -> s[p, p, il, p[text], p]
        # split element parents
        pstart = element.parent.copy()
        pend = element.parent.copy()
        for i,c in enumerate(element.parent.children):
            if c is element:
                break
        pstart.children = pstart.children[:i]
        pend.children = pend.children[i+1:]
        print "action",  [pstart, element, pend]
        grandp = element.parent.parent
        oldparent = element.parent
        grandp.replaceChild(oldparent, [pstart, element, pend])
        assert pstart in grandp.children
        assert element in grandp.children
        assert pend in grandp.children
        assert oldparent not in grandp.children
        assert pstart.parent is grandp
        assert pend.parent is grandp
        #assertparents(element.parent.parent)
        return True # changed
    else:
        for c in element.children:
            if _fixBlockElements(c):
                return True
        
def fixBlockElements(root):
    while _fixBlockElements(root):
        print "_run fix block elements"

def assertparents(e, isroot=True):
    if not isroot:
        assert e.parent
    for c in e.children:
        assertparents(c, isroot=False)


def preprocess(root):
    fixParagraphs(root)
    fixBlockElements(root)
    #fixParagraphs(root)


def main():
    for fn in sys.argv[1:]:
        r = advtree.getAdvTree(fn)
        parser.show(sys.stdout, r)
        preprocess(r)
        parser.show(sys.stdout, r)
        odf = ODFWriter()
        odf.write(r)
        doc = odf.getDoc()
        doc.toXml("%s.xml"%fn)
        doc.save(fn, True)
 
if __name__=="__main__":
    main()
