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

import sys

import odf
import six
from odf import dc, draw, element, math, meta, table, text
from odf.opendocument import OpenDocumentText

from mwlib import advtree, odfconf, parser, writerbase
from mwlib import odfstyles as style
from mwlib.log import Log
from mwlib.mathutils import render_math
from mwlib.treecleaner import TreeCleaner

log = Log("odfwriter")

# check for ODF version
e = element.Element(qname=("a", "n"))

if (
    not hasattr(e, "setAttribute")
    or not hasattr(e, "appendChild")
    or not hasattr(e, "lastChild")
):
    raise ImportError("odfpy version incompatible")

del e

PARENT_NONE_ERROR = "parent is None"


def show_node(obj):
    attrs = list(obj.__dict__.keys())
    log(obj.__class__.__name__)
    stuff = [
        f"{k} => {getattr(obj, k)!r}"
        for k in attrs
        if (k != "children") and getattr(obj, k)
    ]
    if stuff:
        log(repr(stuff))


class SkipChildren:
    "if returned by the writer no children are processed"

    def __init__(self, element=None):
        self.element = element


class ParagraphProxy(text.Element):
    """
    special handling since most problems occure arround paragraphs
    this is broken!
    """

    qname = (text.TEXTNS, "p")

    def addElement(self, handler):
        if hasattr(self, "writeto"):
            raise ValueError("writeto is set")
        if handler.parentNode is not None:
            raise ValueError("already has a parent")
        if handler is self:
            raise ValueError("e is self")

        if isinstance(handler, ParagraphProxy):
            if self.parentNode is None:
                raise ValueError(PARENT_NONE_ERROR)
            self.parentNode.addElement(handler)  # add at the same level
            np = ParagraphProxy()  # add copy at the same level
            np.attributes = self.attributes.copy()
            self.parentNode.addElement(np)
            self.writeto = np

        elif handler.qname not in self.allowed_children:
            if self.parentNode is None:
                raise ValueError(PARENT_NONE_ERROR)
            # log("addElement", e.type, "not allowed in ", self.type)
            # find a parent that accepts this type
            parent = self
            while parent.parentNode is not None and handler.qname not in parent.allowed_children:
                if parent.parentNode is parent:
                    raise ValueError("parent is self")
                parent = parent.parentNode
            if handler.qname not in parent.allowed_children:
                if parent.parentNode is not None:
                    raise ValueError("p.parentNode is not None")
                log(
                    "ParagraphProxy:addElement() ",
                    handler.type,
                    "not allowed in any parents, failed, should have been added to",
                    self.type,
                )
                return
            if parent is self:
                raise ValueError("p is self")
            # add this type to the parent
            parent.addElement(handler)
            # add a new paragraph to this parent and link
            # my addElement and addText to this
            np = ParagraphProxy()
            np.attributes = self.attributes
            parent.addElement(np)
            self.writeto = np
        else:
            text.Element.addElement(self, handler)


"""
we generate odf.text.Elements and
patch them with two specialities:
1) Element.writeto
2) ParagraphProxy(text.Element)
"""


class ODFWriter:
    ignoreUnknownNodes = True
    namedLinkCount = 1

    def __init__(
        self,
        env=None,
        status_callback=None,
        language="en",
        namespace="en.wikipedia.org",
        creator="",
        license="GFDL",
    ):
        self.env = env
        self.status_callback = status_callback
        self.language = language
        self.namespace = namespace
        self.references = []
        self.doc = OpenDocumentText()
        style.apply_styles_to_doc(self.doc)
        self.text = self.doc.text
        self.namedLinkCount = 0
        self.conf = odfconf.OdfConf

        if creator:
            self.doc.meta.addElement(meta.InitialCreator(text=creator))
            self.doc.meta.addElement(dc.Creator(text=creator))
        if language is not None:
            self.doc.meta.addElement(dc.Language(text=language))
        if license is not None:
            self.doc.meta.addElement(meta.UserDefined(name="Rights",
                                                      text=license))

    def writeTest(self, root):
        self.write(root, self.doc.text)

    def writeBook(self, book, output):
        """
        bookParseTree must be advtree and sent through preprocess()
        """

        if self.env and self.env.metabook:
            self.doc.meta.addElement(dc.Title(text=self.env.metabook.get("title", "")))

        for e in book.children:
            self.write(e, self.doc.text)
        doc = self.getDoc()
        doc.save(output, addsuffix=False)
        log("writing to %r" % output)

    def getDoc(self, debuginfo=""):
        return self.doc

    def asstring(self, element=None):
        class Writer:
            def __init__(self):
                self.res = []

            def write(self, txt):
                if isinstance(txt, six.text_type):
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
                log(
                    "writeText:",
                    obj,
                    "not allowed in ",
                    parent.type,
                    "adding Paragraph failed",
                )

    def _save_add_child(self, parent, handler, obj):
        try:
            parent.addElement(handler)
            if handler.parentNode is None:
                raise ValueError(
                    "could not add child"
                )  # this check fails if the child could not be added
            return True
        except odf.element.IllegalChild:
            # fails if paragraph in span:
            # odfwriter >> write: u'text:p' 'not allowed
            # in ' u'text:span' ', dumping'
            try:  # maybe c has no attribute type
                art = obj.get_parent_nodes_by_class(advtree.Article)[0]
                log("in article ", art.caption)
                log("write:", handler.type, "not allowed in ", parent.type,
                    ", dumping")
            except AttributeError:
                log(f"missing .type attribute {handler!r} {parent!r} ")
            return False

    def write(self, obj, parent=None):
        if parent is None:
            raise ValueError("parent is None")

        while hasattr(parent, "writeto"):
            parent = parent.writeto  # SPECIAL HANDLING

        # if its text, append to last node
        if isinstance(obj, parser.Text):
            self.writeText(obj, parent)
        else:
            # check for method
            method_name = "owrite" + obj.__class__.__name__
            method_name = getattr(self, method_name, None)

            if method_name:  # find handler
                handler = method_name(obj)

            elif self.ignoreUnknownNodes:
                log("Handler for node %s not found! SKIPPED" % obj.__class__.__name__)
                show_node(obj)
                handler = None
            else:
                raise ValueError("unknown node:%r" % obj)

            if isinstance(handler, SkipChildren):  # do not process children of this node
                if handler.element is not None:
                    self._save_add_child(parent, handler.element, obj)
                return  # skip
            elif handler is None:
                handler = parent
            else:
                if not self._save_add_child(parent, handler, obj):
                    return

            for child in obj.children[:]:
                self.write(child, handler)

    def writeChildren(self, obj, parent):  # use this to avoid bugs!
        "writes only the children of a node"
        for c in obj:
            self.write(c, parent)

    def owriteArticle(self, a):
        self.references = []  # collect references
        title = a.caption
        log("processing article %s" % title)
        r = text.Section(stylename=style.sect, name=title)  # , display="none")
        r.addElement(text.H(outlinelevel=1, stylename=style.ArticleHeader,
                            text=title))
        return r

    def owriteChapter(self, obj):
        title = obj.caption
        item = text.Section(stylename=style.sect, name=title)
        item.addElement(text.H(outlinelevel=1, text=title,
                               stylename=style.chapter))
        return item

    def owriteSection(self, obj):
        hXstyles = (style.h0, style.h1, style.h2, style.h3, style.h4, style.h5)

        # skip empty sections (as for eg References)
        hasDisplayContent = "".join(
            x.get_all_display_text().strip() for x in obj.children[1:]
        ) or obj.get_child_nodes_by_class(
            advtree.ImageLink
        )  # FIXME, add AdvancedNode.hasContent property
        enabled = False
        if enabled and not hasDisplayContent:  # FIXME
            return SkipChildren()

        title = obj.children[0].get_all_display_text()

        # = is level 0 as in article title =
        # == is level 1 as in mediawiki top level section ==
        # get_section_level() == 1 for most outer section level
        level = 1 + obj.get_section_level()  # min: 1+0 = 1
        level = min(level, len(hXstyles))
        hX = hXstyles[level - 1]

        r = text.Section(stylename=style.sect, name=title)
        r.addElement(text.H(outlinelevel=level, stylename=hX, text=title))
        obj.children = obj.children[1:]
        return r

    def owriteParagraph(self, obj):
        if obj.children:
            imgAsOnlyChild = bool(
                len(obj.children) == 1
                and isinstance(obj.get_first_child(), advtree.ImageLink)
            )
            # handle special case nothing but an image in a paragraph
            if imgAsOnlyChild and isinstance(obj.next, advtree.Paragraph):
                img = obj.get_first_child()
                img.move_to(obj.next.getFirstChild(), prefix=True)
                return SkipChildren()
            return ParagraphProxy(stylename=style.textbody)

    def owriteItem(self, item):
        li = text.ListItem()
        p = ParagraphProxy(stylename=style.textbody)
        li.addElement(p)
        li.writeto = p
        return li

    def owriteItemList(self, lst):
        if lst.numbered:
            return text.List(stylename=style.numberedlist)
        else:
            return text.List(stylename=style.unorderedlist)

    def owriteDefinitionList(self, _):
        return text.List(stylename=style.definitionlist)

    def owriteDefinitionTerm(self, _):
        li = text.ListItem()
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
            def_list = text.List(stylename=style.definitionlist)
            def_list.addElement(li)
            def_list.writeto = p
            return def_list

        return li

    def owriteBreakingReturn(self, _):
        return text.LineBreak()

    def owriteCell(self, _):
        tab = table.TableCell()
        paragraph = ParagraphProxy(stylename=style.textbody)
        tab.addElement(paragraph)
        tab.writeto = paragraph
        # handle rowspan FIXME
        #
        # rs = cell.rowspan
        # if rs:
        #    t.setAttribute(":numberrowsspanned",str(rs))
        return tab

    def owriteRow(self, row):  # COLSPAN FIXME
        tr = table.TableRow()
        for child in row.children:
            col_span = child.colspan
            self.write(child, tr)
            if col_span:
                tr.lastChild.setAttribute("numbercolumnsspanned", str(col_span))
                for _ in range(col_span):
                    tr.addElement(table.CoveredTableCell())
        return SkipChildren(tr)

    def owriteCaption(self, obj):
        # are there caption not in tables ???? FIXME
        if isinstance(obj.parent, advtree.Table):
            return SkipChildren()
        pass  # FIXME

    def owriteTable(self, obj):  # FIXME ADD FORMATTING
        # http://books.evc-cit.info/odbook/ch04.html#text-table-section

        t = table.Table()
        tc = table.TableColumn(
            stylename=style.dumbcolumn, numbercolumnsrepeated=str(obj.numcols)
        )  # FIXME FIXME
        t.addElement(tc)

        captions = [c for c in obj.children if isinstance(c, advtree.Caption)]
        if not captions:  # handle table w/o caption:
            return t
        else:  # a section groups table-caption & table:
            if len(captions) != 1:
                log(
                    "owriteTable: more than one Table Caption not handeled. Using only first Caption!"
                )
            # group using a section
            sec = text.Section(stylename=style.sectTable, name="table section")
            p = ParagraphProxy(stylename=style.tableCaption)
            sec.addElement(p)
            self.writeChildren(captions[0], p)  # only one caption expected and allowed
            sec.addElement(t)
            sec.writeto = t
            return sec

    # ---- inline formattings -------------------
    # use span

    def owriteEmphasized(self, _):
        return text.Span(stylename=style.emphasis)

    def owriteStrong(self, _):
        return text.Span(stylename=style.strong)

    def owriteBold(self, _):
        return text.Span(stylename=style.bold)

    def owriteItalic(self, _):
        return text.Span(stylename=style.italic)

    def owriteSmall(self, _):
        return text.Span(stylename=style.small)

    def owriteBig(self, _):
        return text.Span(stylename=style.big)

    def owriteVar(self, _):
        return text.Span(stylename=style.var)

    def owriteDeleted(self, _):
        return text.Span(stylename=style.deleted)

    def owriteInserted(self, _):
        return text.Span(stylename=style.inserted)

    def owriteRuby(self, _):
        return text.Ruby()

    def owriteRubyText(self, _):
        return text.RubyText()

    def owriteRubyBase(self, _):
        return text.RubyBase()

    def owriteRubyParentheses(self, _):
        pass  # FIXME

    def owriteSub(self, _):
        return text.Span(stylename=style.sub)

    def owriteSup(self, _):
        return text.Span(stylename=style.sup)

    def owriteSpan(self, _):
        return text.Span()

    def owriteOverline(self, _):
        return text.Span(stylename=style.overline)

    def owriteUnderline(self, _):
        return text.Span(stylename=style.underline)

    def owriteStrike(self, _):
        return text.Span(stylename=style.strike)

    def owriteTagNode(self, node):
        if getattr(node, "caption", None) in ["hiero"]:
            return SkipChildren()
        if getattr(node, "caption", None) in ["abbr"]:
            return self.owriteUnderline(node)

    # ------- block formattings -------------------
    # use paragraph

    def owriteCenter(self, _):
        return ParagraphProxy(stylename=style.center)

    def owriteCite(self, _):
        return text.Span(stylename=style.cite)

    def owriteDiv(self, _):
        return ParagraphProxy()

    def owriteTeletyped(self, _):
        # (monospaced) or code, newlines ignored, spaces collapsed
        return text.Span(stylename=style.teletyped)

    def _replaceWhitespaces(self, obj, p):
        # replaces \n, \t and " " given from parser to ODF-valid tags
        # works on (styled) ParagraphProxy p
        rmap = {"\n": text.LineBreak, " ": text.S}
        col = []
        for c in obj.get_all_display_text().replace("\t", " " * 8).strip():
            if c in rmap:
                p.addText("".join(col))
                col = []
                p.addElement(rmap[c]())
            else:
                col.append(c)
        p.addText("".join(col))  # add remaining
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
        return ParagraphProxy(stylename=style.blockquote)

    def owriteIndented(self, s):
        "Writes a indented Paragraph. Margin to the left. Need a lenght of Indented.caption of 1,2 or 3."
        indentStyles = (
            style.indentedSingle,
            style.indentedDouble,
            style.indentedTriple,
        )  # 0, 1, 2
        indentLevel = min(len(s.caption) - 1, len(indentStyles) - 1)
        return ParagraphProxy(stylename=indentStyles[indentLevel])

    def owriteMath(self, obj):
        """
        get a MATHML from Latex
        translate element tree to odf.Elements
        """
        # log("math")
        r = render_math(obj.caption, output_mode="mathml",
                        render_engine="blahtexml")
        if r is None:
            log("render_math failed!")
            return

        def _withETElement(e, parent):
            # translate to odf.Elements
            for c in e:
                node = math.Element(qname=(math.MATHNS, str(c.tag)))
                parent.addElement(node)
                if c.text:
                    text = c.text
                    node.appendChild(odf.element.Text(text))
                    # rffixme: odfpy0.8 errors:"AttributeError:
                    # Element instance has no
                    # attribute 'elements'" -> this is a lie!
                _withETElement(c, node)

        mathframe = draw.Frame(stylename=style.formula, zindex=0,
                               anchortype="as-char")
        mathobject = draw.Object()
        mathframe.addElement(mathobject)
        mroot = math.Math()
        mathobject.addElement(mroot)
        _withETElement(r, mroot)
        return mathframe

    def owriteLink(self, obj):
        a = text.A(href=obj.url or "#")
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

    def owriteSpecialLink(self, obj):  # whats that?
        a = text.A(href=obj.target)
        if not obj.children:
            a.addText(obj.target)
        return a

    def owriteCategoryLink(self, obj):
        if True:  # FIXME, collect and add to the end of the page
            return SkipChildren()

    def owriteLangLink(self, obj):
        return SkipChildren()  # dont want them

    def owriteReference(self, t):
        self.references.append(t)
        node = text.Note(noteclass="footnote")
        nc = text.NoteCitation()
        node.addElement(nc)
        nc.addText(str(len(self.references)))
        nb = text.NoteBody()
        node.addElement(nb)
        p = ParagraphProxy(stylename=style.footnote)
        nb.addElement(p)
        node.writeto = p
        return node

    def owriteReferenceList(self, t):
        # already in odf footnotes
        pass

    def owriteImageMap(self, obj):
        pass  # write children # fixme

    def _size_image(self, width, height, obj):
        """calculate the target image size in inch.
        @param: (w,h): w(idth), h(eight) of image in px
        @type int
        @return: (w,h): w(idth), h(eight) of target image in inch (!)
        @rtype float"""
        if obj.is_inline:
            scale = 1 / self.conf.paper["IMG_DPI_STANDARD"]
        else:
            scale = 1 / self.conf.paper["IMG_DPI_INLINE"]
        w_target = scale * width  # w_target is in inch now
        h_target = scale * height  # h_target is in inch now
        # 2do: obey the value of thumpnail
        if (
            w_target > self.conf.paper["IMG_MAX_WIDTH"]
            or h_target > self.conf.paper["IMG_MAX_HEIGHT"]
        ):
            # image still to large, re-resize to max possible:
            scale = min(
                self.conf.paper["IMG_MAX_WIDTH"] / width,
                self.conf.paper["IMG_MAX_HEIGHT"] / height,
            )
            return (width * scale, height * scale, scale)
        else:
            return (w_target, h_target, scale)

    def owriteImageLink(self, obj, isImageMap=False):
        # see http://books.evc-cit.info/odbook/ch04.html
        # see rl.writer for more advanced image integration,
        # including inline, floating, etc.
        # http://code.pediapress.com/hg/mwlib.rl rlwriter.py

        from PIL import Image as PilImage

        if obj.colon is True:
            return  # writes children
            # fixme: handle isImageMap

        if not self.env or not self.env.images:
            return
            # fixme: handle isImageMap

        imgPath = self.env.images.getDiskPath(obj.target)
        if not imgPath:
            log.warning("invalid image url")
            return
        imgPath = imgPath.encode("utf-8")

        (w_obj, h_obj) = (obj.width or 0, obj.height or 0)
        # sometimes the parser delivers only one value,
        # w or h, so set the other = 0

        try:
            img = PilImage.open(imgPath)
            if img.info.get("interlace", 0) == 1:
                log.warning("got interlaced PNG which can't be handeled by PIL")
                return
        except OSError:
            log.warning("img can not be opened by PIL")
            return

        (w_img, h_img) = img.size

        if w_img == 0 or h_img == 0:
            return

        # sometimes the parser delivers only one value,
        # w or h, so set the other "by hand"
        aspect_ratio = w_img / h_img

        if w_obj > 0 and not h_obj > 0:
            h_obj = w_obj / aspect_ratio
        elif h_obj > 0 and not w_obj > 0:
            w_obj = aspect_ratio / h_obj
        elif w_obj == 0 and h_obj == 0:
            w_obj, h_obj = w_img, h_img
        # hint: w_obj/h_obj are the values of the Thumbnail
        #      w_img/h_img are the real values of the image

        (width, height, scale) = self._size_image(w_obj, h_obj, obj)

        width_in = "%.2fin" % (width)
        height_in = "%.2fin" % (height)

        innerframe = draw.Frame(
            stylename=style.frmInner, width=width_in, height=height_in
        )

        if isImageMap:
            innerframe.w_img = w_img
            innerframe.h_img = h_img
            innerframe.rescaleFactor = (
                scale  # needed cuz image map coordinates needs the same rescaled
            )
            log(f"w_obj ,w_img: {w_obj},{w_img}")

        href = self.doc.addPicture(imgPath)
        innerframe.addElement(draw.Image(href=href))

        if obj.is_inline():
            return SkipChildren(innerframe)  # FIXME something else formatting?
        else:
            innerframe.setAttribute("anchortype", "paragraph")

        width_in = "%.2fin" % (width + style.frmOuter.internSpacing)
        height_in = "%.2fin" % (height)

        # set image alignment
        attrs = {"width": width_in, "anchortype": "paragraph"}
        floats = {
            "right": style.frmOuterRight,
            "center": style.frmOuterCenter,
            "left": style.frmOuterLeft,
        }
        attrs["stylename"] = floats.get(obj.align, style.frmOuterLeft)
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

    def owriteFont(self, _):
        pass  # simply write children

    def owriteNode(self, _):
        pass  # simply write children

    def owriteGallery(self, _):
        pass  # simply write children FIXME

    def owriteHorizontalRule(self, _):
        p = ParagraphProxy(stylename=style.hr)
        return p

    # UNIMPLEMENTED  -----------------------------------------------

    def writeTimeline(self, _):
        raise NotImplementedError

    def writeHiero(self, _):  # FIXME parser support
        raise NotImplementedError


# - func  ---------------------------------------------------


def writer(env, output, status_callback):
    buildbook_status = status_callback.get_sub_range(0,
                                                     50) if status_callback else None
    book = writerbase.build_book(env, status_callback=buildbook_status)

    def scb(status, progress):
        return status_callback is not None and status_callback(
            status=status, progress=progress
        )

    scb(status="preprocessing", progress=50)
    preprocess(book)
    scb(status="rendering", progress=60)
    w = ODFWriter(env, status_callback=scb)
    w.writeBook(book, output=output)


writer.description = "OpenDocument Text"
writer.content_type = "application/vnd.oasis.opendocument.text"
writer.file_extension = "odt"


# - helper funcs   r ---------------------------------------------------


def preprocess(root):
    advtree.build_advanced_tree(root)
    tc = TreeCleaner(root)
    tc.clean_all()


# ==============================================================================


def main():
    for fn in sys.argv[1:]:
        from mwlib.dummydb import DummyDB
        from mwlib.uparser import parse_string

        db = DummyDB()
        with open(fn) as input_file:
            text_input = six.text_type(input_file.read(), "utf8")
        r = parse_string(title=fn, raw=text_input, wikidb=db)
        preprocess(r)
        parser.show(sys.stdout, r)
        odf = ODFWriter()
        odf.writeTest(r)
        doc = odf.getDoc()
        doc.save(fn, True)


if __name__ == "__main__":
    main()
