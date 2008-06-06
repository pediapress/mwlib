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
 * use ODF supported special features for
  * references
  * TableOfContents


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
from mwlib import advtree 
from mwlib import odfstyles as style

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
        # add chapters FIXME
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
        
        print repr(s.buflist), repr(s.buf)
        return s.getvalue()
        #return unicode(s.buf) + ''.join(s.buflist)

    
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
                print  "...failed" 



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
        level = 2 + obj.getSectionLevel() # H2 is max within a page
        #title = u"%d %s" %(level,  obj.children[0].children[0].caption ) # FIXME (debug output)
        title = obj.children[0].children[0].caption
        r = text.Section(stylename=style.sect, name=title) 
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
            # do some other formatting???
            pass
        return text.List(stylename=style.textbody)

    def owriteDefinitionList(self, lst):
        return text.List(stylename=style.textbody)

    def owriteDefinitionTerm(self, obj):
        return self.owriteItem(obj)


    def owriteDefinitionDescription(self, obj):
        li = text.ListItem()
        p = text.P(stylename=style.indented)
        li.addElement(p)

        def _addText(text):
            p.addText(text)

        def _addElement(e):
            p.addElement(e)

        li.addText = _addText
        li.addElement = _addElement
        return li


    def owriteBreakingReturn(self, obj):
        return text.LineBreak()

    def owriteCell(self, cell):
        #self.setVList(td, cell)           
        return table.TableCell()
            
    def owriteRow(self, row): # COLSPAN FIXME
        return table.TableRow()

    def owriteTable(self, t): # FIXME ADD FORMATTING
        t = table.Table()
        tc = table.TableColumn(stylename=style.dumbcolumn) # FIXME FIXME
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
        return text.P(stylename=style.center)

    def owriteCite(self, obj): 
        return text.P(stylename=style.cite)

    def owriteDiv(self, obj): 
        return text.P()

    def owriteTeletyped(self, obj):
        # (monospaced) or code, newlines ignored, spaces collapsed
        return text.P(stylename=style.teletyped)


    def owritePreFormatted(self, n):
        return text.P(stylename=style.preformatted) # FIXME

    def owriteCode(self, obj): 
        return text.P(stylename=style.code)

    def owriteSource(self, obj): 
        return text.P(stylename=style.source)

    
    def owriteBlockquote(self, s):
        "margin to the left & right"
        indentlevel = len(s.caption)-1
        return text.P(stylename=style.blockquote)


    def owriteIndented(self, s):
        "margin to the left"
        indentlevel = len(s.caption)-1
        return text.P(stylename=style.indented)

 
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
        #mathframe.addAttribute("width","2.972cm") # needed to add those attributes in order to see something
        #mathframe.addAttribute("height","1.138cm")
        mathobject = draw.Object() 
        mathframe.addElement(mathobject)
        mroot = math.Math()
        mathobject.addElement(mroot)
        _withETElement(r, mroot)
        return mathframe


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


    def owriteLangLink(self, obj):
        obj.children=[]
        pass # we dont want them in the PDF
    


    def owriteReference(self, t):
        self.references.append(t)
        s =  text.Span(stylename=style.sup)
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
       



    def owriteImageLink(self, obj):
        # see http://books.evc-cit.info/odbook/ch04.html
        # see rl.writer for more advanced image integration, including inline, floating, etc.
        # http://code.pediapress.com/hg/mwlib.rl rlwriter.py
        

        if not self.images:
            return

        targetWidth = 400
        imgPath = self.images.getDiskPath(obj.target, size=targetWidth)
        print imgPath
        if not imgPath:
            print "NO IMAGE PATH", obj, obj.target
            return
        imgPath = imgPath.encode('utf-8')

        width = getattr(obj,"width") or 400
        height = getattr(obj,"height") or 400
        scale = 1/150.  # 1 inch per 150 pix # FIXME CONFIG
        width = "%.2fin" % (width * scale)
        height = "%.2fin" % (height * scale)

        frame = draw.Frame(stylename=style.photo, width=width, height=height, x="1.5cm", y="2.5cm")
        href = self.doc.addPicture(imgPath)
        frame.addElement(draw.Image(href=href))
        return frame

    def writeNode(self, n):
        pass # simply write children


# - unimplemented methods copy from xhtml writer ---------------------------------------------------


    def xwriteHorizontalRule(self, s):
        pass # FIXME

    def setVList(self, element, node): # FIXME N USEME
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
        

    def xwriteGallery(self, obj):
        pass # FIXME

    
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
