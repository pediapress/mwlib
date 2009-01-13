#! /usr/bin/env python

# Copyright (c) 2007-2009 PediaPress GmbH
# See README.txt for additional licensing information.

import os
from mwlib import parser, rendermath, timeline

import urllib
import cgi

from PIL import Image

from mwlib.log import Log

log = Log("htmlwriter")

class HTMLWriter(object):
    imglevel = 0
    namedLinkCount = 1
    def __init__(self, out, images=None, math_renderer=None):
        self.out = out
        self.level = 0
        self.images = images
        # self.images = imgdb.ImageDB(os.path.expanduser("~/images"))
        self.references = []
        if math_renderer is None:
            self.math_renderer = rendermath.Renderer()
        else:
            self.math_renderer = math_renderer
    
    def _write(self, s):
        self.out.write(cgi.escape(s.encode("utf8")))

    def getCategoryList(self, obj):
        categories = list(set(c.target for c in obj.find(parser.CategoryLink)))
        categories.sort()
        return categories
                    
    def write(self, obj):
        m = "write" + obj.__class__.__name__
        m=getattr(self, m, None)
        if not m:
            log.warn("No method to write object:", obj.__class__.__name__)
            return
        m(obj)

    def ignore(self, obj):
        pass

    def serializeVList(self,vlist):
        args = []
        styleArgs = []
        gotClass = 0
        gotExtraClass = 0
        for (key,value) in vlist.items():
            if isinstance(value, (basestring, int)):
                if key=="class":
                    args.append('%s="%s"' % (key, value))
                    gotClass = 1
                else:
                    args.append('%s="%s"' % (key, value))
            if isinstance(value, dict) and key=="style":
                for (_key,_value) in value.items():
                    styleArgs.append("%s:%s" % (_key, _value))
                args.append(' style="%s"' % ';'.join(styleArgs))
                gotExtraClass = 1
        return ' '.join(args)


    def writeMagic(self, m):
        if m.values.get('html'):
            for x in m.children:
                self.write(x)

    def writeSection(self, obj):
        header = "h%s" % (obj.level)
        self.out.write("<%s>" % header)
        self.write(obj.children[0])
        self.out.write("</%s>" % header)
                
        self.level += 1
        for x in obj.children[1:]:
            self.write(x)
        self.level -= 1

    def writePreFormatted(self, n):
        self.out.write("<pre>")
        for x in n:
            self.write(x)
        self.out.write("</pre>")
        
    def writeNode(self, n):
        for x in n:
            self.write(x)

    def writeCell(self, cell):
        svl = ""
        if cell.vlist:
            svl = self.serializeVList(cell.vlist)
            
        self.out.write('<td %s>' % svl)
        for x in cell:
            self.write(x)
        self.out.write("</td>")

    def writeTagNode(self, t):
        if t.caption == 'ref':
            self.references.append(t)
            self.out.write("<sup>%s</sup>" % len(self.references))
            return
        elif t.caption == 'references':
            if not self.references:
                return

            self.out.write("<ol>")
            for r in self.references:
                self.out.write("<li>")
                for x in r:                    
                    self.write(x)
                self.out.write("</li>")
            self.out.write("</ol>")
                           
            self.references = []            
            return
        elif t.caption=='imagemap':
            # FIXME. this is not complete. t.imagemap.entries should also be handled.
            print "WRITEIMAGEMAP:", t.imagemap
            if t.imagemap.imagelink:
                self.write(t.imagemap.imagelink)
            return

        
        self.out.write(t.starttext)
        for x in t:
            self.write(x)
        self.out.write(t.endtext)
            
    def writeRow(self, row):
        self.out.write('<tr>')
        for x in row:
            self.write(x)
            
        self.out.write('</tr>')

    def writeTable(self, t):           
        svl = ""
        if t.vlist:
            svl = self.serializeVList(t.vlist)

        
            
        self.out.write("<table %s>" % svl)
        if t.caption:
            self.out.write("<caption>")
            self.write(t.caption)
            self.out.write("<caption>")
        for x in t:
            self.write(x)
        self.out.write("</table>")

    def writeMath(self, obj):
        latex = obj.caption
        p = self.math_renderer.render(latex)
        self.out.write('<img src="/pngmath/%s/" class="formula">' % os.path.basename(p))

    def writeURL(self, obj):
        self.out.write('<a href="%s" class="hastooltip" ttid="externallink">' % obj.caption)
        if obj.children:
            for x in obj.children:
                self.write(x)
        else:
            self.out.write(obj.caption)
            
        self.out.write('&nbsp;<img src="/resources/outgoing_link.gif" /></a>')

    def writeNamedURL(self, obj):
        self.out.write('<a href="%s" class="hastooltip" ttid="externallink">' % obj.caption)
        if obj.children:
            for x in obj.children:
                self.write(x)
        else:
            name = "[%s]" % self.namedLinkCount
            self.namedLinkCount += 1
            self.out.write(name)
                        
        self.out.write('&nbsp;<img src="/resources/outgoing_link.gif" /></a>')

        
    def writeParagraph(self, obj):
        self.out.write("\n<p>")
        for x in obj:
            self.write(x)
        self.out.write("</p>\n")

    def getHREF(self, obj):
        parts = obj.target.encode('utf-8').split('#')
        parts[0] = parts[0].replace(" ", "_")
        

        return '../%s/' % ("#".join([urllib.quote(x) for x in parts]))

    writeLangLink = ignore

    def writeLink(self, obj):
        if obj.target is None:
            return

        href = self.getHREF(obj)
        if href is not None:
            self.out.write('<a href="%s" class="normallink">' % (href,))
        else:
            self.out.write('<a class="deadlink">')
        if obj.children:
            for x in obj.children:
                self.write(x)
        else:
            self._write(obj.target)
            
        self.out.write("</a>")

    writeArticleLink = writeLink

    def writeSpecialLink(self, obj):
        if obj.children:
            for x in obj.children:
                self.write(x)
        else:
            self._write(obj.target)

    def writeCategoryLink(self, obj):
        if obj.colon:
            if obj.children:
                for x in obj.children:
                    self.write(x)
            else:
                self._write(obj.target)

    def writeTimeline(self, obj):
        img = timeline.drawTimeline(obj.caption)
        if img is None:
            return
        
        target = "/timeline/"+os.path.basename(img)
        width, height = Image.open(img).size
        
        self.out.write('<img src="%s" width="%s" height="%s" />' % (target, width, height))
        
    def writeImageLink(self, obj):
        """
        <span class='image'>
          <span class='left'>
            <img src='bla' />
            <span class='imagecaption'>bla bla</span>
          <span/>
        <span/>
        """
        
        if self.images is None:
            return

        width = obj.width
        height = obj.height

        #if not width:
        #    width = 400  # what could be a sensible default if no width is given? maybe better 0?

        if width:
            path = self.images.getPath(obj.target, size=max(width, height))
        else:
            path = self.images.getPath(obj.target)

        if path is None:
            return

        if isinstance(path, str):
            path = unicode(path, 'utf8')
        targetsrc = '/images/%s' % path
        
        
        if self.imglevel==0:
            self.imglevel += 1

            try:
                def getimg():
                    return Image.open(self.images.getDiskPath(obj.target, size=max(width, height)))
                img = None
                
                if not width:
                    if not img:
                        img = getimg()
                    size = img.size
                    width = min(400, size[0])

                if not height:
                    if not img:
                        img = getimg()
                    size = img.size
                    height = size[1]*width/size[0]
            except IOError, err:
                self.imglevel -= 1
                log.warn("Image.open failed:", err, "path=", repr(path))
                return

            if obj.isInline():
                self.out.write('<img src="%s" width="%s" height="%s" />' % (targetsrc, width, height))
            else:
                align = obj.align
                if obj.thumb == True and not obj.align:
                    obj.align= "clear right"
                self.out.write('''<div  class="bbotstyle image %s" style="width:%spx">'''% (obj.align, width))
                self.out.write('<img src="%s" width="%s" height="%s" />' % (targetsrc, width, height))
                
                self.out.write('<span class="imagecaption">')
                for x in obj.children:
                    self.write(x)
                self.out.write('</span></div>')
            self.imglevel -= 1
        else:
            self.out.write('<a href="%s">' % targetsrc)
            for x in obj.children:
                self.write(x)
            self.out.write('</a>')

    def writeText(self, t):
        #self.out.write(cgi.escape(t.caption).encode('ascii', 'xmlcharrefreplace'))
        self._write(t.caption)
        
    writeControl = writeText

    def writeArticle(self, a):
        if a.caption:
            self.out.write("<h1>")
            self._write(a.caption)
            self.out.write("</h1>")
            
        for x in a:
            self.write(x)

        self.out.write("\n<br/>")
        
    def writeStyle(self, s):
        if s.caption == "''": 
            tag = 'em'
        elif s.caption=="'''''":
            self.out.write("<strong><em>")
            for x in s:
                self.write(x)
            self.out.write("</em></strong>")
            return
        elif s.caption == "'''":
            tag = 'strong'
        elif s.caption == ";":
            self.out.write("<div><strong>")
            for x in s:
                self.write(x)
            self.out.write("</strong></div>")
            return
        
        elif s.caption.startswith(":"):
            self.out.write("<blockquote>"*len(s.caption))
            for x in s:
                self.write(x)
            self.out.write("</blockquote>"*len(s.caption))
            return
        elif s.caption == "overline":
            self.out.write('<u style="text-decoration: overline;">')
            for x in s:
                self.write(x)
            self.out.write('</u>')
            return
        else:
            tag = s.caption
    

        self.out.write("<%s>" % tag)
        for x in s:
            self.write(x)
        self.out.write("</%s>" % tag)

    def writeItem(self, item):
        self.out.write("<li>")
        for x in item:
            self.write(x)
        self.out.write("</li>\n")

    def writeItemList(self, lst):
        if lst.numbered:
            tag = "ol"
        else:
            tag = "ul"
            
        self.out.write("<%s>" % tag)
            
        for x in lst:
            self.write(x)
            self.out.write("\n")

        self.out.write("</%s>" % tag)


class NoLinksWriter(HTMLWriter):
    """Subclass that ignores (non-outgoing) links"""
    
    def writeLink(self, obj):
        if obj.target is None:
            return

        if obj.children:
            for x in obj.children:
                self.write(x)
        else:
            self._write(obj.target)

