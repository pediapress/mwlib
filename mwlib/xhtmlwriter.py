#! /usr/bin/env python

# Copyright (c) 2008, PediaPress GmbH
# See README.txt for additional licensing information.
"""
Generate valid XHTML from the DOM tree generated by the parser.

This implements the proposed format at:
http://www.mediawiki.org/wiki/Extension:XML_Bridge/MWXHTML

Basically XHTML is used adding semantics by using microformats

http://meta.wikimedia.org/wiki/Help:Advanced_editing
http://meta.wikimedia.org/wiki/Help:HTML_in_wikitext

see the corresponding test_xhtmlwriter.py unit test.

if invoked with py.test test_xhtmlwriter.py tests are
executed and xhtml output is validated by xmllint.


ToDo: 
 * write more tests
 * reorder tree to fix for paragraphs / have to fix parser first
 * templates / parser has to support marking of boundaries first
 * always add vlist data if available / if supported by the parser
 * strategy to move to xhtml1.1 in order to validate w/ mathml
"""

import sys
import xml.etree.ElementTree as ET
from mwlib import parser,  mathml
from mwlib.log import Log
import advtree 

log = Log("xhtmlwriter")

def showNode(obj):
    attrs = obj.__dict__.keys()
    log(obj.__class__.__name__ ) 
    stuff =  ["%s => %r" %(k,getattr(obj,k)) for k in attrs if 
              (not k == "children") and getattr(obj,k)
              ]
    if stuff:
        log(repr(stuff))


def indent(elem, level=0):
    i = u"\n" + level*u"  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + u"  "
        for elem in elem:
            indent(elem, level+1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i



class MWXHTMLWriter(object):
    namedLinkCount = 1

    header='''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
'''
    def __init__(self, language="en", namespace="en.wikipedia.org", imagesrcresolver=None):
        self.language = language
        self.namespace = namespace
        self.imagesrcresolver = imagesrcresolver # e.g. "http://anyhost/redir?img=IMAGENAME" where IMAGENAME is substituted

        self.references = []
        self.root = ET.Element("html")
        self.root.set("xmlns", "http://www.w3.org/1999/xhtml")
        self.root.set("xml:lang", "en")
        #if self.language: self.root.set("lang", self.language) 
        self.xmlparent = None # this is the parent XML Element
        
        self.errors = []
        self.languagelinks = []
        self.categorylinks = []
        
        
    def getTree(self, debuginfo=""):
        indent(self.root) # breaks XHTML (proper rendering at least) if activated!
        # generate xml for
        # errors
        # categorylinks
        # language links
        return self.root
    
    def asstring(self):
        return self.header + ET.tostring(self.getTree())

    
    def writeText(self, obj, parent):
        if parent.getchildren(): # add to tail of last tag
            t = parent.getchildren()[-1]
            if not t.tail:
                t.tail = obj.caption
            else:
                t.tail += obj.caption
        else:
            if not parent.text:
                parent.text = obj.caption
            else:
                parent.text += obj.caption


    def write(self, obj, parent=None):
        #showNode(obj)
        # if its text, append to last node
        if isinstance(obj, parser.Text):
            self.writeText(obj, parent)
        else:
            # check for method
            m = "xwrite" + obj.__class__.__name__
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
                    e.append(ce)
            return e


    def xwriteLink(self, obj): # FIXME (known|unknown)
        a = ET.Element("a")
        if obj.target:
            a.set("href", obj.target)
            a.set("class", "mwx.link.article")
        if not obj.children:
            a.text = obj.target
        return a

    def xwriteArticle(self, a):
        # add head + title
        h = ET.SubElement(self.root,"head")
        e = ET.SubElement(h, "title")
        if a.caption:
            e.text = a.caption

        # start body
        return ET.SubElement(self.root,"body")


    def xwriteSection(self, obj):
        e = ET.Element("div")
        e.set("class", "mwx.section")
        level = 1 + obj.getLevel()
        h = ET.SubElement(e, "h%d" % level)
        self.write(obj.children[0], h)
        obj.children = obj.children[1:]
        return e

        
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
    blockelements = set("p","pre", "ul", "ol","blockquote", "hr", "dl")
    # TODO POSTPROCESS 



def preprocess(root):
    pass

def main():
    for fn in sys.argv[1:]:
        r = advtree.getAdvTree(fn)
        preprocess(r)
        parser.show(sys.stdout, r)
        dbw = MWXHTMLWriter()
        dbw.write(r)
        nf = open("%s.html" % fn, "w")
        nf.write(dbw.asstring())
        
 
if __name__=="__main__":
    main()
