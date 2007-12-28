#! /usr/bin/env python

# Copyright (c) 2008, PediaPress GmbH
# See README.txt for additional licensing information.

"""
we use XHTML 1.0 and add our own mwx xmlns for MW specialities.
"""



"""
ToDo: 
 * language info in html decl
 * internal links
 * TEMPLATES
 * Redirect
 * References?
"""



import os
import sys
import types
import xml.etree.ElementTree as ET
from mwlib import parser, rendermath # , timeline
from mathml import latex2mathml


def log(err):
    sys.stderr.write(err + " ")
    pass


def showNode(obj):
    attrs = obj.__dict__.keys()
    log(obj.__class__.__name__ ) 
    stuff =  ["%s => %r" %(k,getattr(obj,k)) for k in attrs if 
              (not k == "children") and getattr(obj,k)
              ]
    if stuff:
        log(repr(stuff))
    log("\n")


def indent(elem, level=0):
    i = "\n" + level*"  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
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
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
 "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">'''

    def __init__(self, language="en", namespace="en.wikipedia.org"):
        self.references = []
        self.root = ET.Element("html")
        self.root.set("xmlns", "http://www.w3.org/1999/xhtml")
        self.root.set("xmlns:mwx","http://pediapress.com/2007/MediaWikiXML/mwx")
        self.root.set("xml:lang", "en")
        self.root.set("lang", language) 
        self.namespace = namespace
        self.xmlparent = None # this is the parent XML Element

    def getTree(self):
        self.annotateSections()
        indent(self.root)
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
        if obj.__class__.__name__ == "Text":
            self.writeText(obj, parent)
            assert len(obj.children) == 0
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
            a.set("mwx:linktype", "article")
        if not obj.children:
            a.text = obj.target
        return a


    def xwriteRedirect(self, r):
        # find header add redirect meta
        pass

    def xwriteArticle(self, a):
        # add head + title
        h = ET.SubElement(self.root,"head")
        ET.SubElement(h, "meta", mwx_namespace=self.namespace)
        e = ET.SubElement(h, "title")
        if a.caption:
            e.text = a.caption

        # start body
        return ET.SubElement(self.root,"body")


    def xwriteSection(self, obj):
        e = ET.Element("mwx:section")
        h = ET.SubElement(e, "h")
        self.write(obj.children[0], h)
        obj.children = obj.children[1:]
        return e


    def annotateSections(self):
        def r(node, sectionlevel):
            if node.tag == "mwx:section":
                sectionlevel += 1
                node.set("level", str(sectionlevel))
            if node.tag == "h":
                node.tag = "h%d" % sectionlevel
            for c in node.getchildren():
                r(c, sectionlevel)
        r(self.root,0)



    def xwriteMagic(self, m): # FIXME
        return ET.Element("mwx:magic")

    def xwritePreFormatted(self, n):
        return ET.Element("pre")
        
    def xwriteNode(self, n):
        pass # simply write children


    def xwriteParagraph(self, obj):
        return ET.Element("p")

    def xwriteCell(self, cell):
        td = ET.Element("td")
        if cell.vlist:
            for k,v in self.xserializeVList(cell.vlist):
                td.set(k,v)
        return td

            
    def xwriteRow(self, row):
        return ET.Element("tr")

    def xwriteTable(self, t):           

        table = ET.Element("table")
        if t.vlist:
            for k,v in self.xserializeVList(t.vlist):
                table.set(k,v)
            
        if t.caption:
            c = ET.SubElement(table, "caption")
            self.writeText(t.caption, c)
        return table


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


    def xwriteTagNode(self, t):
        if t.caption == 'ref':
            self.references.append(t)
            t =  ET.Element("sup")
            t.set("mwx:noteref", len(self.references))
            t.text = unicode( len(self.references))
            return t

        elif t.caption == 'references':
            if not self.references:
                return
            ol = ET.Element("ol")
            for i,r in enumerate(self.references):
                li = ET.SubElement(ol,"li")
                li.set("mwx:note", i+1) 
                for x in r:                    
                    self.write(x, li)                          
            
            self.references = []            
            return
        
        # parse html and return ET elements
        p =  ET.fromstring(t.starttext + t.endtext)
        return p



    def xwriteMath(self, obj):
        "adds mathml w/ namespace"
        # FIXME, return verbose error
        r = latex2mathml(obj.caption)
        if not r:
            r = ET.Element("mwx:math", error="an error occured in blahtexml")
            r.text = obj.caption
        return r

    # Links ---------------------------------------------------------

    """
    missing Linktypes:
    * intra-page / mwx:linktype="fragment"
    * mwx:linktype known|unknown (shall we provide this info?) yes?
    * mwx:linktype media
    * mwx:linktype self
    """

    def xwriteTemplate(self, obj): # FIXME
        """
        <mwx:template pagename="templatename">
          <mwx:argument>X</mwx:argument>
          <mwx:argument>Y</mwx:argument>
        </mwx:template>
        """
        # REALLY UNSOLVED!
        pass

    def xwriteURL(self, obj):
        a = ET.Element("a", href=obj.caption)
        a.set("mwx:linktype", "external")
        if not obj.children:
            a.text = obj.caption
        return a

    def xwriteNamedURL(self, obj):
        a = ET.Element("a", href=obj.caption)
        a.set("mwx:linktype", "external")
        if not obj.children:
            name = "[%s]" % self.namedLinkCount
            self.namedLinkCount += 1
            a.text = name
        return a


    def xwriteSpecialLink(self, obj): # whats that?
        if not obj.children:
            a = ET.Element("a", href=obj.target)
            a.set("mwx:linktype", "special")
            a.text = obj.target
        else:
            a = ET.Element("mwx:debug")
            a.text = "special link w/ children"
        return a

    def xwriteCategoryLink(self, obj):
        if not obj.colon and not obj.children:
            a = ET.Element("a", href=obj.target)
            a.set("mwx:linktype", "category")
            a.text = obj.target
            return a


    def xwriteLangLink(self, obj): # FIXME no valid url (but uri)
        if obj.target is None:
            return
        a = ET.Element("a", href=obj.target)
        a.set("mwx:linktype", "interwiki")
        if not obj.children:
            a.text = obj.target
        return a


    def xwriteTimeline(self, obj): 
        s = ET.Element("mwx:timeline")
        s.text = obj.caption
        return s

    def xwriteHiero(self, obj): # FIXME parser support
        s = ET.Element("mwx:hiero")
        s.text = obj.caption
        return s

    def xwriteImageLink(self, obj): # FIXME
        i = e = ET.Element("mwx:image")
        if obj.isInline():
            i.set("mwx:imageextra", "inline")
        if obj.thumb:
            i.set("mwx:imageextra", "thumb")    
        if obj.caption or obj.align:
            e = ET.SubElement(e, "div")
            if obj.align:
                e.set("align", obj.align)
            if obj.caption:
                e.text = img.caption

        href ="/wiki/Image:" + obj.target # i18n
        e = ET.SubElement(e, "a", href=href)
        e.set("mwx:linktype", "image")
        #e = ET.SubElement(e, "img", sec=href)
        return i

    #xwriteControl = writeText # FIXME
        
    def xwriteStyle(self, s):
        if s.caption == "''": 
            tag = 'em'
        elif s.caption=="'''''":
            e = ET.Element("strong")
            e = ET.SubElement(e, "em")
            return e
        elif s.caption == "'''":
            tag = 'strong'
        elif s.caption == ";":
            e = ET.Element("div")
            e = ET.SubElement(e, "strong")
            return e        
        elif s.caption.startswith(":"):
            e = ET.Element("blockquote")
            for i in range(len(s.caption)-1):
                e = ET.SubElement(e, "blockquote")
            return e
        elif s.caption == "overline":
            return ET.Element("u", style="text-decoration: overline;")
        else:
            tag = s.caption
    
        return ET.Element(tag)


    def xwriteItem(self, item):
        return ET.Element("li")

    def xwriteItemList(self, lst):
        if lst.numbered:
            tag = "ol"
        else:
            tag = "ul"
        return ET.Element(tag)



def main():
    from mwlib.dummydb import DummyDB
    db = DummyDB()
    
    for x in sys.argv[1:]:
        input = unicode(open(x).read(), 'utf8')
        
        if True: 
            from mwlib import expander
            te = expander.Expander(input, pagename=x, wikidb=db)
            input = te.expandTemplates()
        
        tokens = parser.tokenize(x, input)
        
        p = parser.Parser(tokens, os.path.basename(x))
        r = p.parse()

        parser.show(sys.stderr, r, 0)
        
        dbw = MWXHTMLWriter()
        dbw.write(r)
        print dbw.asstring()
        
 
if __name__=="__main__":
    main()
