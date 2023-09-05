#! /usr/bin/env python
#! -*- coding:utf-8 -*-

# Copyright (c) 2007, PediaPress GmbH
# See README.txt for additional licensing information.

import time
from builtins import str

from PIL import Image
from reportlab.lib.pagesizes import A3
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.platypus.doctemplate import BaseDocTemplate, PageTemplate
from reportlab.platypus.frames import Frame
from reportlab.platypus.paragraph import Paragraph

from mwlib.rl import pdfstyles
from mwlib.rl.customflowables import TocEntry
from mwlib.rl.formatter import RLFormatter
from mwlib.rl.pdfstyles import (
    footer_margin_hor,
    footer_margin_vert,
    header_margin_hor,
    header_margin_vert,
    page_height,
    page_margin_bottom,
    page_margin_left,
    page_margin_right,
    page_margin_top,
    page_width,
    pagefooter,
    print_height,
    print_width,
    serif_font,
    text_style,
    titlepagefooter,
)

from . import fontconfig, locale

font_switcher = fontconfig.RLFontSwitcher()
font_switcher.font_paths = fontconfig.font_paths
font_switcher.register_default_font(pdfstyles.default_font)
font_switcher.registerFontDefinitionList(fontconfig.fonts)

formatter = RLFormatter(font_switcher=font_switcher)


def _doNothing(canvas, doc):
    "Dummy callback for onPage"
    pass


class SimplePage(PageTemplate):
    def __init__(self, pageSize=A3):
        id = "simplepage"
        # frames = Frame(0, 0, pageSize[0], pageSize[1])
        pw = pageSize[0]
        ph = pageSize[1]
        frames = Frame(
            page_margin_left,
            page_margin_bottom,
            pw - page_margin_left - page_margin_right,
            ph - page_margin_top - page_margin_bottom,
        )

        PageTemplate.__init__(self, id=id, frames=frames, pagesize=pageSize)


class WikiPage(PageTemplate):
    def __init__(
        self,
        title=None,
        id=None,
        onPage=_doNothing,
        onPageEnd=_doNothing,
        pagesize=(page_width, page_height),
        rtl=False,
    ):
        """
        @type title: unicode
        """

        id = title
        frames = Frame(page_margin_left, page_margin_bottom, print_width, print_height)

        PageTemplate.__init__(
            self, id=id, frames=frames, onPage=onPage, onPageEnd=onPageEnd, pagesize=pagesize
        )

        self.title = title
        self.rtl = rtl

    def beforeDrawPage(self, canvas, doc):
        canvas.setFont(serif_font, 10)
        canvas.setLineWidth(0)
        # header
        canvas.line(
            header_margin_hor,
            page_height - header_margin_vert,
            page_width - header_margin_hor,
            page_height - header_margin_vert,
        )
        if pdfstyles.show_page_header:
            canvas.saveState()
            canvas.resetTransforms()
            h_offset = header_margin_hor if not self.rtl else 1.5 * header_margin_hor
            canvas.translate(h_offset, page_height - header_margin_vert - 0.1 * cm)
            p = Paragraph(self.title, text_style())
            p.canv = canvas
            p.wrap(
                page_width - header_margin_hor * 2.5, page_height
            )  # add an extra 0.5 margin to have enough space for page number
            p.drawPara()
            canvas.restoreState()

        if not self.rtl:
            h_pos = page_width - header_margin_hor
            d = canvas.drawRightString
        else:
            h_pos = header_margin_hor
            d = canvas.drawString
        d(h_pos, page_height - header_margin_vert + 0.1 * cm, "%d" % doc.page)

        # Footer
        canvas.saveState()
        canvas.setFont(serif_font, 8)
        canvas.line(
            footer_margin_hor,
            footer_margin_vert,
            page_width - footer_margin_hor,
            footer_margin_vert,
        )
        if pdfstyles.show_page_footer:
            p = Paragraph(formatter.clean_text(pagefooter, escape=False), text_style())
            p.canv = canvas
            w, h = p.wrap(page_width - header_margin_hor * 2.5, page_height)
            p.drawOn(canvas, footer_margin_hor, footer_margin_vert - 10 - h)
        canvas.restoreState()


class TitlePage(PageTemplate):
    def __init__(
        self,
        cover=None,
        id=None,
        onPage=_doNothing,
        onPageEnd=_doNothing,
        pagesize=(page_width, page_height),
    ):

        id = "TitlePage"
        p = pdfstyles
        frames = Frame(
            p.title_margin_left,
            p.title_margin_bottom,
            p.page_width - p.title_margin_left - p.title_margin_right,
            p.page_height - p.title_margin_top - p.title_margin_bottom,
        )

        PageTemplate.__init__(
            self, id=id, frames=frames, onPage=onPage, onPageEnd=onPageEnd, pagesize=pagesize
        )
        self.cover = cover

    def _scale_img(self, img_area_size, img_fn):
        img = Image.open(self.cover)
        img_width, img_height = img.size
        img_area_width = min(page_width, img_area_size[0])
        img_area_height = min(page_height, img_area_size[1])
        img_ar = img_width / img_height
        img_area_ar = img_area_width / img_area_height
        if img_ar >= img_area_ar:
            return (img_area_width, img_area_width / img_ar)
        else:
            return (img_area_height * img_ar, img_area_height)

    def beforeDrawPage(self, canvas, doc):
        canvas.setFont(serif_font, 8)
        canvas.saveState()
        if pdfstyles.show_title_page_footer:
            canvas.line(
                footer_margin_hor,
                footer_margin_vert,
                page_width - footer_margin_hor,
                footer_margin_vert,
            )
            footertext = [_(titlepagefooter)]
            if pdfstyles.show_creation_date:
                locale.setlocale(locale.LC_ALL, "")
                footertext.append(
                    pdfstyles.creation_date_txt
                    % time.strftime(pdfstyles.creation_date_format, time.localtime())
                )
            lines = [formatter.clean_text(line, escape=False) for line in footertext]
            txt = "<br/>".join(
                line if isinstance(line, str) else str(line, "utf-8") for line in lines
            )
            p = Paragraph(txt, text_style(mode="footer"))
            w, h = p.wrap(print_width, print_height)
            canvas.translate((page_width - w) / 2.0, footer_margin_vert - h - 0.25 * cm)
            p.canv = canvas
            p.draw()
        canvas.restoreState()
        if self.cover:
            width, height = self._scale_img(pdfstyles.title_page_image_size, self.cover)
            if pdfstyles.title_page_image_pos[0] is None:
                x = (page_width - width) / 2.0
            else:
                x = max(0, min(page_width - width, pdfstyles.title_page_image_pos[0]))
            if pdfstyles.title_page_image_pos[1] is None:
                y = (page_height - height) / 2.0
            else:
                y = max(0, min(page_height - height, pdfstyles.title_page_image_pos[1]))
            canvas.drawImage(self.cover, x, y, width, height)





class PPDocTemplate(BaseDocTemplate):
    def __init__(self, output, status_callback=None, tocCallback=None, **kwargs):
        self.bookmarks = []
        BaseDocTemplate.__init__(self, output, **kwargs)
        if status_callback:
            self.estimatedDuration = 0
            self.progress = 0
            self.setProgressCallBack(self.progressCB)
            self.status_callback = status_callback
        self.tocCallback = tocCallback
        self.title = kwargs["title"]

    def progressCB(self, typ, value):
        if typ == "SIZE_EST":
            self.estimatedDuration = int(value)
        if typ == "PROGRESS":
            self.progress = 100 * int(value) / self.estimatedDuration
        if typ == "PAGE":
            self.status_callback(progress=self.progress, page=value)

    def beforeDocument(self):
        if self.title:
            self.page = -1

    def _startBuild(self, filename=None, canvasmaker=canvas.Canvas):
        BaseDocTemplate._startBuild(self, filename=filename, canvasmaker=canvasmaker)

        type2lvl = {
            "Chapter": 0,
            "article": 1,
            "heading2": 2,
            "heading3": 3,
            "heading4": 4,
        }
        got_chapter = False
        last_lvl = 0
        for (bm_id, (bm_title, bm_type)) in enumerate(self.bookmarks):
            lvl = type2lvl[bm_type]
            if bm_type == "Chapter":
                got_chapter = True
            elif not got_chapter:  # outline-lvls can't start above zero
                lvl -= 1
            lvl = min(lvl, last_lvl + 1)
            last_lvl = lvl
            self.canv.addOutlineEntry(bm_title, str(bm_id), lvl, bm_type == "article")

    def afterFlowable(self, flowable):
        """Our rule for the table of contents is simply to take
        the text of H1, H2 and H3 elements. We broadcast a
        notification to the DocTemplate, which should inform
        the TOC and let it pull them out."""
        if not self.tocCallback:
            return
        if flowable.__class__ == TocEntry:
            self.tocCallback((flowable.lvl, flowable.txt, self.page))
