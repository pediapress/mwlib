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
import logging
import sys

import odf
from odf import dc, draw, element, math, meta, table, text
from odf.opendocument import OpenDocumentText

from mwlib import parser
from mwlib.parser import Caption, advtree
from mwlib.parser.dummydb import DummyDB
from mwlib.parser.refine.uparser import parse_string
from mwlib.parser.treecleaner import TreeCleaner
from mwlib.rendering import writerbase
from mwlib.rendering.mathutils import render_math
from mwlib.writers.odf import odfconf
from mwlib.writers.odf import odfstyles as style

log = logging.getLogger("odfwriter")

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
    log.info(obj.__class__.__name__)
    stuff = [
        f"{k} => {getattr(obj, k)!r}"
        for k in attrs
        if (k != "children") and getattr(obj, k)
    ]
    if stuff:
        log.info(repr(stuff))


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
            paragraph_proxy = ParagraphProxy()  # add copy at the same level
            paragraph_proxy.attributes = self.attributes.copy()
            self.parentNode.addElement(paragraph_proxy)
            self.writeto = paragraph_proxy

        elif handler.qname not in self.allowed_children:
            if self.parentNode is None:
                raise ValueError(PARENT_NONE_ERROR)
            # log.debug("addElement", e.type, "not allowed in ", self.type)
            # find a parent that accepts this type
            parent = self
            while (
                parent.parentNode is not None
                and handler.qname not in parent.allowed_children
            ):
                if parent.parentNode is parent:
                    raise ValueError("parent is self")
                parent = parent.parentNode
            if handler.qname not in parent.allowed_children:
                if parent.parentNode is not None:
                    raise ValueError("p.parentNode is not None")
                log.info(
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
            paragraph_proxy = ParagraphProxy()
            paragraph_proxy.attributes = self.attributes
            parent.addElement(paragraph_proxy)
            self.writeto = paragraph_proxy
        else:
            text.Element.addElement(self, handler)


# we generate odf.text.Elements and
# patch them with two specialities:
# 1) Element.writeto
# 2) ParagraphProxy(text.Element)


class ODFWriter:
    ignoreUnknownNodes = True
    named_link_count = 1

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
        self.named_link_count = 0
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

    def writeBook(self, book, output):
        """
        bookParseTree must be advtree and sent through preprocess()
        """

        if self.env and self.env.metabook:
            self.doc.meta.addElement(dc.Title(text=self.env.metabook.get("title", "")))

        for child in book.children:
            self.write(child, self.doc.text)
        doc = self.getDoc()
        doc.save(output, addsuffix=False)
        log.info(f"writing to {output}")

    def getDoc(self, _=""):
        return self.doc

    def asstring(self, element=None):
        class Writer:
            def __init__(self):
                self.res = []

            def write(self, txt):
                if isinstance(txt, str):
                    self.res.append(str(txt))
                else:
                    self.res.append(txt)

            def getvalue(self):
                return "".join(self.res)

        writer = Writer()
        if not element:
            element = self.doc.text
        element.toXml(0, writer)

        return writer.getvalue()

    def writeText(self, obj, parent):
        try:
            parent.addText(obj.caption)
        except odf.element.IllegalText:
            paragraph_proxy = ParagraphProxy(stylename=style.textbody)
            try:
                parent.addElement(paragraph_proxy)
                paragraph_proxy.addText(obj.caption)
            except odf.element.IllegalChild:
                log.info(
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
                log.info("in article %s", art.caption)
                log.info(f"write: {handler.type} not allowed in {parent.type}, dumping")
            except AttributeError:
                log.info(f"missing .type attribute {handler!r} {parent!r} ")
            return False

    def _handle_object_and_determine_child_processing(self, obj, parent):
        should_return = False
        # check for method
        method_name = "owrite" + obj.__class__.__name__
        method_name = getattr(self, method_name, None)

        if method_name:  # find handler
            handler = method_name(obj)

        elif self.ignoreUnknownNodes:
            log.info("Handler for node %s not found! SKIPPED" % obj.__class__.__name__)
            show_node(obj)
            handler = None
        else:
            raise ValueError("unknown node:%r" % obj)

        if isinstance(
            handler, SkipChildren
        ):  # do not process children of this node
            if handler.element is not None:
                self._save_add_child(parent, handler.element, obj)
            should_return = True
        elif handler is None:
            handler = parent
        else:
            if not self._save_add_child(parent, handler, obj):
                should_return = True
        return handler, should_return

    def write(self, obj, parent=None):
        if parent is None:
            raise ValueError("parent is None")

        while hasattr(parent, "writeto"):
            parent = parent.writeto  # SPECIAL HANDLING

        # if its text, append to last node
        if isinstance(obj, parser.Text):
            self.writeText(obj, parent)
        else:
            handler, should_return = self._handle_object_and_determine_child_processing(obj, parent)
            if should_return:
                return

            for child in obj.children[:]:
                self.write(child, handler)

    def writeChildren(self, obj, parent):  # use this to avoid bugs!
        "writes only the children of a node"
        for child in obj:
            self.write(child, parent)

    def owriteArticle(self, article):
        self.references = []  # collect references
        title = article.caption
        log.info("processing article %s" % title)
        section = text.Section(stylename=style.sect, name=title)
        section.addElement(
            text.H(outlinelevel=1, stylename=style.ArticleHeader, text=title)
        )
        return section

    def owriteChapter(self, obj):
        title = obj.caption
        item = text.Section(stylename=style.sect, name=title)
        item.addElement(text.H(outlinelevel=1, text=title, stylename=style.chapter))
        return item

    def owriteSection(self, obj):
        hx_styles = (style.h0, style.h1, style.h2, style.h3, style.h4, style.h5)

        # skip empty sections (as for eg References)
        has_display_content = "".join(
            x.get_all_display_text().strip() for x in obj.children[1:]
        ) or obj.get_child_nodes_by_class(
            advtree.ImageLink
        )  # FIXME, add AdvancedNode.hasContent property
        enabled = False
        if enabled and not has_display_content:  # FIXME
            return SkipChildren()

        title = obj.children[0].get_all_display_text()

        # = is level 0 as in article title =
        # == is level 1 as in mediawiki top level section ==
        # get_section_level() == 1 for most outer section level
        level = 1 + obj.get_section_level()  # min: 1+0 = 1
        level = min(level, len(hx_styles))
        hx_style = hx_styles[level - 1]

        section = text.Section(stylename=style.sect, name=title)
        section.addElement(text.H(outlinelevel=level, stylename=hx_style, text=title))
        obj.children = obj.children[1:]
        return section

    def owriteParagraph(self, obj):
        if obj.children:
            img_as_only_child = bool(
                len(obj.children) == 1
                and isinstance(obj.get_first_child(), advtree.ImageLink)
            )
            # handle special case nothing but an image in a paragraph
            if img_as_only_child and isinstance(obj.next, advtree.Paragraph):
                img = obj.get_first_child()
                img.move_to(obj.next.getFirstChild(), prefix=True)
                return SkipChildren()
            return ParagraphProxy(stylename=style.textbody)

    def owriteItem(self, _):
        list_item = text.ListItem()
        paragraph_proxy = ParagraphProxy(stylename=style.textbody)
        list_item.addElement(paragraph_proxy)
        list_item.writeto = paragraph_proxy
        return list_item

    def owriteItemList(self, lst):
        if lst.numbered:
            return text.List(stylename=style.numberedlist)
        return text.List(stylename=style.unorderedlist)

    def owriteDefinitionList(self, _):
        return text.List(stylename=style.definitionlist)

    def owriteDefinitionTerm(self, _):
        list_item = text.ListItem()
        paragraph_proxy = ParagraphProxy(stylename=style.definitionterm)
        list_item.addElement(paragraph_proxy)
        list_item.writeto = paragraph_proxy
        return list_item

    def owriteDefinitionDescription(self, obj):
        list_item = text.ListItem()
        paragraph_proxy = ParagraphProxy(stylename=style.indentedSingle)
        list_item.addElement(paragraph_proxy)
        list_item.writeto = paragraph_proxy
        # FIXME, this should be handled in advtree!
        if not isinstance(obj.parent, advtree.DefinitionList):
            def_list = text.List(stylename=style.definitionlist)
            def_list.addElement(list_item)
            def_list.writeto = paragraph_proxy
            return def_list

        return list_item

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
        table_row = table.TableRow()
        for child in row.children:
            col_span = child.colspan
            self.write(child, table_row)
            if col_span:
                table_row.lastChild.setAttribute("numbercolumnsspanned", str(col_span))
                for _ in range(col_span):
                    table_row.addElement(table.CoveredTableCell())
        return SkipChildren(table_row)

    def owriteCaption(self, obj):
        # are there caption not in tables ???? FIXME
        if isinstance(obj.parent, advtree.Table):
            return SkipChildren()
        return None

    def owriteTable(self, obj):  # FIXME ADD FORMATTING
        # http://books.evc-cit.info/odbook/ch04.html#text-table-section

        new_table = table.Table()
        column = table.TableColumn(
            stylename=style.dumbcolumn, numbercolumnsrepeated=str(obj.numcols)
        )  # FIXME FIXME
        new_table.addElement(column)

        captions = [c for c in obj.children if isinstance(c, Caption)]
        if not captions:  # handle table w/o caption:
            return new_table
        # a section groups table-caption & table:
        if len(captions) != 1:
            log.info(
                "owriteTable: more than one Table Caption not handeled. Using only first Caption!"
            )
        # group using a section
        sec = text.Section(stylename=style.sectTable, name="table section")
        paragraph_proxy = ParagraphProxy(stylename=style.tableCaption)
        sec.addElement(paragraph_proxy)
        self.writeChildren(captions[0], paragraph_proxy)  # only one caption expected and allowed
        sec.addElement(new_table)
        sec.writeto = new_table
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
        return None

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

    def _replace_whitespaces(self, obj, paragraph_proxy):
        # replaces \n, \t and " " given from parser to ODF-valid tags
        # works on (styled) ParagraphProxy p
        rmap = {"\n": text.LineBreak, " ": text.S}
        col = []
        for char in obj.get_all_display_text().replace("\t", " " * 8).strip():
            if char in rmap:
                paragraph_proxy.addText("".join(col))
                col = []
                paragraph_proxy.addElement(rmap[char]())
            else:
                col.append(char)
        paragraph_proxy.addText("".join(col))  # add remaining
        obj.children = []  # remove the children
        return paragraph_proxy

    def owritePreFormatted(self, obj):
        paragraph_proxy = ParagraphProxy(stylename=style.preformatted)
        return self._replace_whitespaces(obj, paragraph_proxy)

    def owriteSource(self, obj):
        paragraph_proxy = ParagraphProxy(stylename=style.source)
        return self._replace_whitespaces(obj, paragraph_proxy)

    def owriteCode(self, _):
        return text.Span(stylename=style.code)

    def owriteBlockquote(self, _):
        "margin to the left & right"
        return ParagraphProxy(stylename=style.blockquote)

    def owriteIndented(self, input_string):
        "Writes a indented Paragraph. Margin to the left. Need a lenght of Indented.caption of 1,2 or 3."
        indent_styles = (
            style.indentedSingle,
            style.indentedDouble,
            style.indentedTriple,
        )  # 0, 1, 2
        indent_level = min(len(input_string.caption) - 1, len(indent_styles) - 1)
        return ParagraphProxy(stylename=indent_styles[indent_level])

    def owriteMath(self, obj):
        """
        get a MATHML from Latex
        translate element tree to odf.Elements
        """
        # log.info("math")
        rendered_math = render_math(obj.caption, output_mode="mathml", render_engine="blahtexml")
        if rendered_math is None:
            log.info("render_math failed!")
            return

        def _with_et_element(element, parent):
            # translate to odf.Elements
            for child in element:
                node = math.Element(qname=(math.MATHNS, str(child.tag)))
                parent.addElement(node)
                if child.text:
                    text = child.text
                    node.appendChild(odf.element.Text(text))
                    # rffixme: odfpy0.8 errors:"AttributeError:
                    # Element instance has no
                    # attribute 'elements'" -> this is a lie!
                _with_et_element(child, node)

        mathframe = draw.Frame(stylename=style.formula, zindex=0, anchortype="as-char")
        mathobject = draw.Object()
        mathframe.addElement(mathobject)
        mroot = math.Math()
        mathobject.addElement(mroot)
        _with_et_element(rendered_math, mroot)
        return mathframe

    def owriteLink(self, obj):
        hyperlink_element = text.A(href=obj.url or "#")
        if not obj.children:
            hyperlink_element.addText(obj.target)
        return hyperlink_element

    owriteArticleLink = owriteLink
    obwriteLangLink = owriteLink
    owriteNamespaceLink = owriteLink
    owriteInterwikiLink = owriteLink

    def owriteURL(self, obj):
        hyperlink_element = text.A(href=obj.caption)
        if not obj.children:
            hyperlink_element.addText(obj.caption)
        return hyperlink_element

    def owriteNamedURL(self, obj):
        # FIXME handle references
        hyperlink_element = text.A(href=obj.caption)
        if not obj.children:
            name = "[%s]" % self.named_link_count
            self.named_link_count += 1
            hyperlink_element.addText(name)
        return hyperlink_element

    def owriteSpecialLink(self, obj):  # whats that?
        hyperlink_element = text.A(href=obj.target)
        if not obj.children:
            hyperlink_element.addText(obj.target)
        return hyperlink_element

    def owriteCategoryLink(self, _):
        # FIXME, collect and add to the end of the page
        return SkipChildren()

    def owriteLangLink(self, _):
        return SkipChildren()  # dont want them

    def owriteReference(self, footnote_text):
        self.references.append(footnote_text)
        node = text.Note(noteclass="footnote")
        note_citation = text.NoteCitation()
        node.addElement(note_citation)
        note_citation.addText(str(len(self.references)))
        note_body = text.NoteBody()
        node.addElement(note_body)
        paragraph_proxy = ParagraphProxy(stylename=style.footnote)
        note_body.addElement(paragraph_proxy)
        node.writeto = paragraph_proxy
        return node

    def owriteReferenceList(self, footnote_text):
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
        return (w_target, h_target, scale)

    def _determine_image_path_or_write_children(self, obj):
        if obj.colon is True:
            return None  # writes children
            # fixme: handle isImageMap

        if not self.env or not self.env.images:
            return None
            # fixme: handle isImageMap

        img_path = self.env.images.get_disk_path(obj.target)
        if not img_path:
            log.warning("invalid image url")
            return None
        img_path = img_path.encode("utf-8")
        return img_path

    def _calculate_object_dimensions_based_on_aspect_ratio(self, w_obj, h_obj, w_img, h_img, aspect_ratio):
        if w_obj > 0 and not h_obj > 0:
            h_obj = w_obj / aspect_ratio
        elif h_obj > 0 and not w_obj > 0:
            w_obj = aspect_ratio / h_obj
        elif w_obj == 0 and h_obj == 0:
            w_obj, h_obj = w_img, h_img
        return w_obj, h_obj

    def owriteImageLink(self, obj, is_image_map=False):
        # see http://books.evc-cit.info/odbook/ch04.html
        # see rl.writer for more advanced image integration,
        # including inline, floating, etc.
        # http://code.pediapress.com/hg/mwlib.rl rlwriter.py

        from PIL import Image as PilImage

        img_path = self._determine_image_path_or_write_children(obj)
        if not img_path:
            return

        (w_obj, h_obj) = (obj.width or 0, obj.height or 0)
        # sometimes the parser delivers only one value,
        # w or h, so set the other = 0

        try:
            img = PilImage.open(img_path)
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

        (w_obj, h_obj) = self._calculate_object_dimensions_based_on_aspect_ratio(w_obj, h_obj, w_img, h_img, aspect_ratio)
        # hint: w_obj/h_obj are the values of the Thumbnail
        #      w_img/h_img are the real values of the image

        (width, height, scale) = self._size_image(w_obj, h_obj, obj)

        width_in = f"{width:.2f}in"
        height_in = f"{height:.2f}in"

        innerframe = draw.Frame(
            stylename=style.frmInner, width=width_in, height=height_in
        )

        if is_image_map:
            innerframe.w_img = w_img
            innerframe.h_img = h_img
            innerframe.rescaleFactor = (
                scale  # needed cuz image map coordinates needs the same rescaled
            )
            log.info(f"w_obj ,w_img: {w_obj},{w_img}")

        href = self.doc.addPicture(img_path)
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

        text_box = draw.TextBox()
        frame.addElement(text_box)
        paragraph_proxy = ParagraphProxy(stylename=style.imgCaption)
        text_box.addElement(paragraph_proxy)
        paragraph_proxy.addElement(innerframe)
        frame.writeto = paragraph_proxy
        if is_image_map:
            frame.writeImageMapTo = innerframe
        return frame

    def owriteFont(self, _):
        pass  # simply write children

    def owriteNode(self, _):
        pass  # simply write children

    def owriteGallery(self, _):
        pass  # simply write children FIXME

    def owriteHorizontalRule(self, _):
        paragraph_proxy = ParagraphProxy(stylename=style.hr)
        return paragraph_proxy

    # UNIMPLEMENTED  -----------------------------------------------

    def writeTimeline(self, _):
        raise NotImplementedError

    def writeHiero(self, _):  # FIXME parser support
        raise NotImplementedError


# - func  ---------------------------------------------------


def writer(env, output, status_callback):
    buildbook_status = status_callback.get_sub_range(0, 50) if status_callback else None
    book = writerbase.build_book(env, status_callback=buildbook_status)

    def scb(status, progress):
        return status_callback is not None and status_callback(
            status=status, progress=progress
        )

    scb(status="preprocessing", progress=50)
    preprocess(book)
    scb(status="rendering", progress=60)
    odf_writer = ODFWriter(env, status_callback=scb)
    odf_writer.writeBook(book, output=output)


writer.description = "OpenDocument Text"
writer.content_type = "application/vnd.oasis.opendocument.text"
writer.file_extension = "odt"


# - helper funcs   r ---------------------------------------------------


def preprocess(root):
    advtree.build_advanced_tree(root)
    tree_cleaner = TreeCleaner(root)
    tree_cleaner.clean_all()


# ==============================================================================


def main():
    for filename in sys.argv[1:]:
        database = DummyDB()
        with open(filename) as input_file:
            text_input = str(input_file.read(), "utf8")
        parsed_string = parse_string(title=filename, raw=text_input, wikidb=database)
        preprocess(parsed_string)
        parser.show(sys.stdout, parsed_string)
        odf = ODFWriter()
        odf.writeTest(parsed_string)
        doc = odf.getDoc()
        doc.save(filename, True)


if __name__ == "__main__":
    main()
