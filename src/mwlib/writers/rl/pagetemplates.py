#! /usr/bin/env python

# Copyright (c) 2007, PediaPress GmbH
# See README.txt for additional licensing information.

import locale
import time
from gettext import gettext as _

from PIL import Image
from reportlab.lib.pagesizes import A3
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.platypus.doctemplate import BaseDocTemplate, PageTemplate
from reportlab.platypus.frames import Frame
from reportlab.platypus.paragraph import Paragraph

from mwlib.writers.rl import fontconfig, pdfstyles
from mwlib.writers.rl.customflowables import TocEntry
from mwlib.writers.rl.formatter import RLFormatter
from mwlib.writers.rl.pdfstyles import (
    FOOTER_MARGIN_HOR,
    FOOTER_MARGIN_VER,
    HEADER_MARGIN_HOR,
    HEADER_MARGIN_VERT,
    PAGE_FOOTER,
    PAGE_HEIGHT,
    PAGE_MARGIN_BOTTOM,
    PAGE_MARGIN_LEFT,
    PAGE_MARGIN_RIGHT,
    PAGE_MARGIN_TOP,
    PAGE_WIDTH,
    PRINT_HEIGHT,
    PRINT_WIDTH,
    SERIF_FONT,
    TITLE_PAGE_FOOTER,
    text_style,
)

font_switcher = fontconfig.RLFontSwitcher()
font_switcher.font_paths = fontconfig.font_paths
font_switcher.register_default_font(pdfstyles.DEFAULT_FONT)
font_switcher.register_font_def_list(fontconfig.fonts)

formatter = RLFormatter(font_switcher=font_switcher)


def _do_nothing(canvas, doc):
    "Dummy callback for onPage"
    pass


class SimplePage(PageTemplate):
    def __init__(self, pageSize=A3):
        page_id = "simplepage"
        page_width = pageSize[0]
        page_height = pageSize[1]
        frames = Frame(
            PAGE_MARGIN_LEFT,
            PAGE_MARGIN_BOTTOM,
            page_width - PAGE_MARGIN_LEFT - PAGE_MARGIN_RIGHT,
            page_height - PAGE_MARGIN_TOP - PAGE_MARGIN_BOTTOM,
        )

        PageTemplate.__init__(self, id=page_id,
                              frames=frames, pagesize=pageSize)


class WikiPage(PageTemplate):
    def __init__(
        self,
        title=None,
        id=None,
        onPage=_do_nothing,
        onPageEnd=_do_nothing,
        pagesize=(PAGE_WIDTH, PAGE_HEIGHT),
        rtl=False,
    ):
        """
        @type title: unicode
        """

        page_id = title
        frames = Frame(PAGE_MARGIN_LEFT, PAGE_MARGIN_BOTTOM,
                       PRINT_WIDTH, PRINT_HEIGHT)

        PageTemplate.__init__(
            self,
            id=page_id,
            frames=frames,
            onPage=onPage,
            onPageEnd=onPageEnd,
            pagesize=pagesize,
        )

        self.title = title
        self.rtl = rtl

    def beforeDrawPage(self, canvas, doc):
        canvas.setFont(SERIF_FONT, 10)
        canvas.setLineWidth(0)
        # header
        canvas.line(
            HEADER_MARGIN_VERT,
            PAGE_HEIGHT - HEADER_MARGIN_VERT,
            PAGE_WIDTH - HEADER_MARGIN_HOR,
            PAGE_HEIGHT - HEADER_MARGIN_VERT,
        )
        if pdfstyles.SHOW_PAGE_HEADER:
            canvas.saveState()
            canvas.resetTransforms()
            h_offset = HEADER_MARGIN_HOR if not self.rtl else 1.5 * HEADER_MARGIN_HOR
            canvas.translate(h_offset,
                             PAGE_HEIGHT - HEADER_MARGIN_VERT - 0.1 * cm)
            paragraph = Paragraph(self.title, text_style())
            paragraph.canv = canvas
            paragraph.wrap(
                PAGE_WIDTH - HEADER_MARGIN_HOR * 2.5, PAGE_HEIGHT
            )  # add an extra 0.5 margin to have enough space for page number
            paragraph.drawPara()
            canvas.restoreState()

        if not self.rtl:
            h_pos = PAGE_WIDTH - HEADER_MARGIN_HOR
            draw_str = canvas.drawRightString
        else:
            h_pos = HEADER_MARGIN_HOR
            draw_str = canvas.drawString
        draw_str(h_pos, PAGE_HEIGHT - HEADER_MARGIN_VERT + 0.1 * cm, "%d" % doc.page)

        # Footer
        canvas.saveState()
        canvas.setFont(SERIF_FONT, 8)
        canvas.line(
            FOOTER_MARGIN_HOR,
            FOOTER_MARGIN_VER,
            PAGE_WIDTH - FOOTER_MARGIN_HOR,
            FOOTER_MARGIN_VER,
        )
        if pdfstyles.SHOW_PAGE_FOOTER:
            paragraph = Paragraph(formatter.clean_text(PAGE_FOOTER,
                                                       escape=False),
                                  text_style())
            paragraph.canv = canvas
            _, height = paragraph.wrap(PAGE_WIDTH - HEADER_MARGIN_HOR * 2.5,
                                       PAGE_HEIGHT)
            paragraph.drawOn(canvas, FOOTER_MARGIN_HOR,
                             FOOTER_MARGIN_VER - 10 - height)
        canvas.restoreState()


class TitlePage(PageTemplate):
    def __init__(
        self,
        cover=None,
        id=None,
        onPage=_do_nothing,
        onPageEnd=_do_nothing,
        pagesize=(PAGE_WIDTH, PAGE_HEIGHT),
    ):
        page_id = "TitlePage"
        frames = Frame(
            pdfstyles.TITLE_MARGIN_LEFT,
            pdfstyles.TITLE_MARGIN_BOTTOM,
            pdfstyles.PAGE_WIDTH - pdfstyles.TITLE_MARGIN_LEFT - pdfstyles.TITLE_MARGIN_RIGHT,
            pdfstyles.PAGE_HEIGHT - pdfstyles.TITLE_MARGIN_TOP - pdfstyles.TITLE_MARGIN_BOTTOM,
        )

        PageTemplate.__init__(
            self,
            id=page_id,
            frames=frames,
            onPage=onPage,
            onPageEnd=onPageEnd,
            pagesize=pagesize,
        )
        self.cover = cover

    def _scale_img(self, img_area_size, _):
        img = Image.open(self.cover)
        img_width, img_height = img.size
        img_area_width = min(PAGE_WIDTH, img_area_size[0])
        img_area_height = min(PAGE_HEIGHT, img_area_size[1])
        img_ar = img_width / img_height
        img_area_ar = img_area_width / img_area_height
        if img_ar >= img_area_ar:
            return (img_area_width, img_area_width / img_ar)
        return (img_area_height * img_ar, img_area_height)

    def beforeDrawPage(self, canvas, template):
        canvas.setFont(SERIF_FONT, 8)
        canvas.saveState()
        if pdfstyles.SHOW_TITLE_PAGE_FOOTER:
            canvas.line(
                FOOTER_MARGIN_HOR,
                FOOTER_MARGIN_VER,
                PAGE_WIDTH - FOOTER_MARGIN_HOR,
                FOOTER_MARGIN_VER,
            )
            footertext = [_(TITLE_PAGE_FOOTER)]
            if pdfstyles.SHOW_CREATION_DATE:
                locale.setlocale(locale.LC_ALL, "")
                footertext.append(
                    pdfstyles.CREATION_DATE_TXT
                    % time.strftime(pdfstyles.CREATION_DATE_FORMAT,
                                    time.localtime())
                )
            lines = [formatter.clean_text(line,
                                          escape=False) for line in footertext]
            txt = "<br/>".join(
                line if isinstance(line,
                                   str) else str(line,
                                                 "utf-8") for line in lines
            )
            paragraph = Paragraph(txt, text_style(mode="footer"))
            width, height = paragraph.wrap(PRINT_WIDTH, PRINT_HEIGHT)
            canvas.translate((PAGE_WIDTH - width) / 2.0,
                             FOOTER_MARGIN_VER - height - 0.25 * cm)
            paragraph.canv = canvas
            paragraph.draw()
        canvas.restoreState()
        if self.cover:
            width, height = self._scale_img(pdfstyles.TITLE_PAGE_IMAGE_SIZE,
                                            self.cover)
            if pdfstyles.TITLE_PAGE_IMAGE_POS[0] is None:
                x_cord = (PAGE_WIDTH - width) / 2.0
            else:
                x_cord = max(0, min(PAGE_WIDTH - width,
                                    pdfstyles.TITLE_PAGE_IMAGE_POS[0]))
            if pdfstyles.TITLE_PAGE_IMAGE_POS[1] is None:
                y_cord = (PAGE_HEIGHT - height) / 2.0
            else:
                y_cord = max(0, min(PAGE_HEIGHT - height,
                                    pdfstyles.TITLE_PAGE_IMAGE_POS[1]))
            canvas.drawImage(self.cover, x_cord, y_cord, width, height)


class PPDocTemplate(BaseDocTemplate):
    def __init__(self, output, status_callback=None,
                 toc_callback=None, **kwargs):
        self.bookmarks = []
        BaseDocTemplate.__init__(self, output, **kwargs)
        if status_callback:
            self.estimated_duration = 0
            self.progress = 0
            self.setProgressCallBack(self.progress_callback)
            self.status_callback = status_callback
        self.toc_callback = toc_callback
        self.title = kwargs["title"]
        self.page = 0

    def progress_callback(self, typ, value):
        if typ == "SIZE_EST":
            self.estimated_duration = int(value)
        if typ == "PROGRESS":
            self.progress = 100 * int(value) / self.estimated_duration
        if typ == "PAGE":
            self.status_callback(progress=self.progress, page=value)

    def beforeDocument(self):
        if self.title:
            self.page = -1

    def _startBuild(self, filename=None, canvasmaker=canvas.Canvas):
        BaseDocTemplate._startBuild(self,
                                    filename=filename, canvasmaker=canvasmaker)

        type2lvl = {
            "Chapter": 0,
            "article": 1,
            "heading2": 2,
            "heading3": 3,
            "heading4": 4,
        }
        got_chapter = False
        last_lvl = 0
        for bm_id, (bm_title, bm_type) in enumerate(self.bookmarks):
            lvl = type2lvl[bm_type]
            if bm_type == "Chapter":
                got_chapter = True
            elif not got_chapter:  # outline-lvls can't start above zero
                lvl -= 1
            lvl = min(lvl, last_lvl + 1)
            last_lvl = lvl
            self.canv.addOutlineEntry(bm_title,
                                      str(bm_id), lvl, bm_type == "article")

    def afterFlowable(self, flowable):
        """Our rule for the table of contents is simply to take
        the text of H1, H2 and H3 elements. We broadcast a
        notification to the DocTemplate, which should inform
        the TOC and let it pull them out."""
        if not self.toc_callback:
            return
        if flowable.__class__ == TocEntry:
            self.toc_callback((flowable.lvl, flowable.txt, self.page))
