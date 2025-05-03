#! /usr/bin/env python

# Copyright (c) 2007, PediaPress GmbH
# See README.txt for additional licensing information.

import re
import string
import urllib.error
import urllib.parse
import urllib.request

from reportlab.lib.colors import Color
from reportlab.platypus.flowables import (
    Flowable,
    HRFlowable,
    Image,
    PageBreak,
    Preformatted,
    _ContainerSpace,
    _flowableSublist,
    _listWrapOn,
)
from reportlab.platypus.paragraph import Paragraph, cleanBlockQuotedText, deepcopy

from mwlib.writers.rl import pdfstyles


class Figure(Flowable):
    def __init__(
        self,
        img_file,
        caption_txt,
        caption_style,
        img_width=None,
        img_height=None,
        margin=(0, 0, 0, 0),
        padding=(0, 0, 0, 0),
        align=None,
        border_color=(0.75, 0.75, 0.75),
        no_mask=False,
        url=None,
    ):
        img_file = img_file
        self.img_path = img_file
        # workaround for http://code.pediapress.com/wiki/ticket/324
        # see http://two.pairlist.net/pipermail/reportlab-users/2008-October/007526.html
        if no_mask:
            self.i = Image(img_file, width=img_width, height=img_height, mask=None)
        else:
            self.i = Image(img_file, width=img_width, height=img_height)
        self.img_width = img_width
        self.img_height = img_height
        self.paragraph = Paragraph(caption_txt, style=caption_style)
        self.margin = margin  # 4-tuple. margins in order: top, right, bottom, left
        self.padding = padding  # same as above
        self.border_color = border_color
        self.align = align
        self.caption_style = caption_style
        self.caption_txt = caption_txt
        self.avail_width = None
        self.avail_height = None
        self.url = url

    def draw(self):
        canv = self.canv
        if self.align == "center":
            canv.translate((self.avail_width - self.width / 2), 0)
        canv.saveState()
        canv.setStrokeColor(
            Color(self.border_color[0], self.border_color[1], self.border_color[2])
        )
        canv.rect(self.margin[3], self.margin[2], self.box_width, self.box_height)
        canv.restoreState()
        canv.translate(
            self.margin[3] + self.padding[3], self.margin[2] + self.padding[2] - 2
        )
        self.paragraph.canv = canv
        self.paragraph.draw()
        canv.translate(
            (self.box_width - self.padding[1] - self.padding[3] - self.i.drawWidth) / 2,
            self.caption_height + 2,
        )
        self.i.canv = canv
        self.i.draw()
        if self.url:
            frags = urllib.parse.urlsplit(self.url)
            clean_url = urllib.parse.urlunsplit(
                (
                    frags.scheme,
                    frags.netloc,
                    urllib.parse.quote(frags.path, safe="/"),
                    urllib.parse.quote(frags.query, safe="=&"),
                    frags.fragment,
                )
            )
            canv.linkURL(
                clean_url,
                (0, 0, self.img_width, self.img_height),
                relative=1,
                thickness=0,
            )

    def wrap(self, avail_width, avail_height):
        self.avail_width = avail_width
        self.avail_height = avail_height
        content_width = max(
            self.i.drawWidth, self.paragraph.wrap(self.i.drawWidth, avail_height)[0]
        )
        self.box_width = content_width + self.padding[1] + self.padding[3]
        (self.caption_width, self.caption_height) = self.paragraph.wrap(
            content_width, avail_height
        )
        self.caption_height += (
            self.caption_style.spaceBefore + self.caption_style.spaceAfter
        )
        self.box_height = (
            self.i.drawHeight + self.caption_height + self.padding[0] + self.padding[2]
        )
        self.width = self.box_width + self.margin[1] + self.margin[3]
        self.height = self.box_height + self.margin[0] + self.margin[2]
        return (self.width, self.height)


def get_figure_size(figure, avail_width, avail_height):
    width, height = figure.wrap(avail_width, avail_height)
    return width, height


def get_paragraph_width(paragraph):
    return (
        paragraph.style.leftIndent
        + paragraph.style.rightIndent
        + paragraph.width
    )


def get_float_width(full_width, max_width):
    return full_width - max_width


def get_n_float_lines(total_hf, para_heights, leading):
    return max(0, int((total_hf - (sum(para_heights))) / leading))


def get_auto_leading_height(paragraph):
    auto_leading = (
        paragraph.style.auto_leading
        if hasattr(paragraph, "style")
        else ""
    )
    if (
        hasattr(paragraph, "style")
        and auto_leading == "max"
        and paragraph.blPara.kind == 1
    ):
        p_height = 0
        for line in paragraph.blPara.lines:
            p_height += (
                max(line.ascent - line.descent, paragraph.style.leading) * 1.025
            )  # magic factor! auto_leading==max increases line-height
    else:
        if auto_leading == "max":
            p_height = len(paragraph.blPara.lines) * max(
                paragraph.style.leading, 1.2 * paragraph.style.fontSize
            )  # used to be 1.2 instead of 1.0
        else:
            p_height = len(paragraph.blPara.lines) * paragraph.style.leading
    return p_height


def get_paragraph_height(paragraph):
    return (
        len(paragraph.blPara.lines) * paragraph.style.leading
        + paragraph.style.spaceBefore
        + paragraph.style.spaceAfter
    )


def handle_hr_flowable(self, avail_width, max_width, total_hf):
    self.para_heights.append(1)
    self._offsets.append(0)
    if (total_hf - (sum(self.para_heights))) > 0:
        self.horizontal_rule_offsets.append(max_width)
    else:
        self.horizontal_rule_offsets.append(0)


def handle_inline_image(self, paragraph, float_width, n_float_lines, max_width, full_width):
    self.resize_inline_image(paragraph, float_width)
    paragraph.width = 0
    if hasattr(paragraph, "blPara"):
        del paragraph.blPara
    if hasattr(paragraph, "style") and paragraph.style.wordWrap == "CJK":
        paragraph.blPara = paragraph.breakLinesCJK(
            n_float_lines * [float_width] + [full_width]
        )
    else:
        paragraph.blPara = paragraph.breakLines(
            n_float_lines * [float_width] + [full_width]
        )
    if self.fig_align == "left":
        self._offsets.append([max_width] * (n_float_lines) + [0])


def handle_paragraph(self, paragraph, full_width, max_width, total_hf):
    float_width = get_float_width(full_width, max_width)
    n_float_lines = get_n_float_lines(total_hf, self.para_heights, paragraph.style.leading)
    handle_inline_image(self, paragraph, float_width, n_float_lines, max_width, full_width)
    auto_leading_height = get_auto_leading_height(paragraph)
    paragraph_height = get_paragraph_height(paragraph)
    self.para_heights.append(paragraph_height + auto_leading_height)


class FiguresAndParagraphs(Flowable):
    """takes a list of figures and paragraphs and floats the figures
    next to the paragraphs.
    current limitations:
     * all figures are floated on the same side as the first image
     * the biggest figure-width is used as the text-margin
    """

    def __init__(self, figures, paragraphs, figure_margin=(0, 0, 0, 0), rtl=False):
        self.figures = figures
        self.figure_margin = figure_margin
        self.paragraphs = paragraphs
        self.fig_align = figures[
            0
        ].align  # fixme: all figures will be aligned like the first figure
        if not self.fig_align:
            self.fig_align = "left" if rtl else "right"
        for figure in self.figures:
            if self.fig_align == "left":
                figure.margin = pdfstyles.IMG_MARGINS_FLOAT_LEFT
            else:  # default figure alignment is right
                figure.margin = pdfstyles.IMG_MARGINS_FLOAT_RIGHT
        self.wfs = []  # width of figures
        self.hfs = []  # height of figures
        self.rtl = rtl  # Flag that indicates if document is set right-to-left

    def _get_v_offset(self):
        for paragraph in self.paragraphs:
            if hasattr(paragraph, "style") and hasattr(paragraph.style, "spaceBefore"):
                return paragraph.style.spaceBefore
        return 0

    def resize_inline_image(self, paragraph, float_width):
        if paragraph.text is None:
            return
        img_dims = re.findall(
            '<img.*?width="([0-9.]+)pt".*?height="([0-9.]+)pt".*?/>', paragraph.text
        )
        if img_dims:
            txt = paragraph.text
            changed = False
            for width, height in img_dims:
                if float(width) < float_width:
                    continue
                changed = True
                new_h = float(height) * float_width / float(width)
                new_w = float_width
                txt = txt.replace('width="%spt"' % width, 'width="%.2fpt"' % new_w)
                txt = txt.replace('height="%spt"' % height, 'height="%.2fpt"' % new_h)
            if changed:
                paragraph._setup(
                    txt,
                    paragraph.style,
                    paragraph.bulletText,
                    None,
                    cleanBlockQuotedText,
                )

    def wrap(self, avail_width, avail_height):
        max_width = 0
        self.wfs = []
        self.hfs = []
        self.horizontal_rule_offsets = []
        total_hf = self._get_v_offset()
        for figure in self.figures:
            width, height = get_figure_size(figure, avail_width, avail_height)
            total_hf += height
            max_width = max(max_width, width)
            self.wfs.append(width)
            self.hfs.append(height)

        self.para_heights = []
        self._offsets = []
        for paragraph in self.paragraphs:
            if isinstance(paragraph, HRFlowable):
                handle_hr_flowable(self, avail_width, max_width, total_hf)
                continue

            full_width = get_paragraph_width(paragraph)
            handle_paragraph(self, paragraph, full_width, max_width, total_hf)

        self.width = avail_width
        self.height = max(sum(self.para_heights), total_hf)
        return (avail_width, self.height)

    def draw_figures(self, canv, horizontal_offsets, vertical_offset):
        for i, figure in enumerate(self.figures):
            vertical_offset += self.hfs[i]
            figure.drawOn(canv, horizontal_offsets[i], self.height - vertical_offset)
        return vertical_offset

    def draw_paragraphs(self, canv, count, paragraph):
        canv.translate(0, -paragraph.style.spaceBefore)
        paragraph.canv = canv
        paragraph.draw()
        canv.translate(0, -self.para_heights[count] + paragraph.style.spaceBefore)

    def handle_paragraph_offset(self, paragraph, count):
        if self.fig_align == "left":
            paragraph._offsets = self._offsets[count]
            if hasattr(paragraph, "style") and hasattr(paragraph.style, "bulletIndent"):
                if not self.rtl:
                    paragraph.style.bulletIndent += paragraph._offsets[0]
                else:
                    paragraph.style.bulletIndent -= (self.paragraphs[0]._offsets[0] - 34)

    def handle_horizontal_rule(self, canv, paragraph, width_offset):
        paragraph.canv = canv
        if self.fig_align == "left":
            canv.translate(width_offset, 0)
        paragraph.wrap(self.width - width_offset, self.height)
        paragraph.draw()

    def handle_paragraph(self, canv, count, paragraph):
        self.handle_paragraph_offset(paragraph, count)
        if isinstance(paragraph, HRFlowable):
            width_offset = self.horizontal_rule_offsets.pop(0)
            self.handle_horizontal_rule(canv, paragraph, width_offset)
        else:
            self.draw_paragraphs(canv, count, paragraph)

    def draw(self):
        canv = self.canv
        canv.saveState()
        vertical_offset = self._get_v_offset()
        if self.fig_align == "left":
            horizontal_offsets = [0] * len(self.figures)
        else:
            horizontal_offsets = [self.width - wf for wf in self.wfs]

        vertical_offset = self.draw_figures(canv, horizontal_offsets, vertical_offset)

        for count, paragraph in enumerate(self.paragraphs):
            self.handle_paragraph(canv, count, paragraph)

        canv.restoreState()

    def get_fitting_figures(self, avail_height):
        fitting_figures = []
        height = self._get_v_offset()
        for i, figure in enumerate(self.figures):
            if (height + self.hfs[i]) < avail_height:
                fitting_figures.append(figure)
            else:
                break
            height += self.hfs[i]
        return fitting_figures, height

    def should_force_split(self, i, avail_height, height):
        if hasattr(self.paragraphs[i], "style") and getattr(
            self.paragraphs[i].style, "prevent_post_pagebreak", False
        ):
            if len(self.paragraphs) > i + 1 and hasattr(self.paragraphs, "style"):
                line_height = self.paragraphs[i + 1].style.leading
            else:
                line_height = pdfstyles.LEADING
            if (
                len(self.paragraphs) > i + 1
                and (
                    height
                    + self.para_heights[i]
                    + pdfstyles.MIN_LINES_AFTER_HEADING * line_height
                )
                > avail_height
            ):
                return True
        return False

    def _handle_paragraph_splitting(self, i, avail_height, height, avail_width,
                                    splitted_paragraph, force_split,
                                    paragraph, fitting_paras):
        if splitted_paragraph:
            return force_split, splitted_paragraph
        if self.should_force_split(i, avail_height, height):
            force_split = True
        para_frags = paragraph.split(
            avail_width,
            avail_height
            - height
            - paragraph.style.spaceBefore
            - paragraph.style.spaceAfter
            - 2 * paragraph.style.leading,
        )  # one line-height "safety margin"
        splitted_paragraph = True
        if len(para_frags) == 2:
            fitting_paras.append(para_frags[0])
            return force_split, splitted_paragraph
        elif len(para_frags) < 2:
            return force_split, splitted_paragraph
        else:  # fixme: not sure if splitting a paragraph can yield more than two elements...
            return force_split, splitted_paragraph

    def get_fitting_paragraphs(self, avail_height, avail_width):
        fitting_paras = []
        height = 0
        splitted_paragraph = False
        force_split = False
        for i, paragraph in enumerate(self.paragraphs):
            if (height + self.para_heights[i]) < avail_height and not force_split:
                fitting_paras.append(paragraph)
            else:
                force_split, splitted_paragraph = self._handle_paragraph_splitting(i, avail_height, height,
                                                                                   avail_width, splitted_paragraph,
                                                                                   force_split, paragraph, fitting_paras)
                break
            height += self.para_heights[i]
        return fitting_paras, height

    def split(self, avail_width, avail_height):
        if (
            not hasattr(self, "hfs")
            or len(self.hfs) == 0
            or hasattr(self, "keep_together_split")
        ):
            self.wrap(avail_width, avail_height)

        fitting_figures, height = self.get_fitting_figures(avail_height)
        fitting_paras, height = self.get_fitting_paragraphs(avail_height, avail_width)

        if height < avail_height:
            next_elements = self.paragraphs[len(fitting_paras):]
        else:
            next_elements = self.figures[len(fitting_figures):] + self.paragraphs[
                len(fitting_paras):
            ]

        return [
            FiguresAndParagraphs(
                fitting_figures, fitting_paras, figure_margin=self.figure_margin
            )
        ] + next_elements


class PreformattedBox(Preformatted):
    def __init__(self, text, style, margin=4, padding=4, borderwidth=0.1, **kwargs):
        Preformatted.__init__(self, text, style, **kwargs)
        self.margin = margin
        self.padding = padding
        self.borderwidth = borderwidth

    def wrap(self, avail_width, avail_height):
        width, height = Preformatted.wrap(self, avail_width, avail_height)
        return (
            width + self.margin + self.borderwidth + self.padding * 2,
            height + self.margin + self.borderwidth + self.padding * 2,
        )

    def draw(self):
        self.canv.saveState()
        self.canv.setLineWidth(self.borderwidth)
        self.canv.translate(0, self.margin)
        self.canv.rect(0, 0, self.width, self.height + self.padding * 2)
        self.canv.translate(0, self.style.spaceAfter)
        Preformatted.draw(self)
        self.canv.restoreState()

    def split(self, avail_width, avail_height):
        if avail_height < self.style.leading:
            return []

        lines_that_fit = int(
            (avail_height - self.padding - self.margin) * 1.0 / self.style.leading
        )

        text1 = string.join(self.lines[0:lines_that_fit], "\n")
        text2 = string.join(self.lines[lines_that_fit:], "\n")
        style = self.style
        if style.firstLineIndent != 0:
            style = deepcopy(style)
            style.firstLineIndent = 0
        return [
            PreformattedBox(
                text1,
                style,
                margin=self.margin,
                padding=self.padding,
                borderwidth=self.borderwidth,
            ),
            PreformattedBox(
                text2,
                style,
                margin=self.margin,
                padding=self.padding,
                borderwidth=self.borderwidth,
            ),
        ]


class SmartKeepTogether(_ContainerSpace, Flowable):
    def __init__(self, flowables, max_height=None):
        self._content = _flowableSublist(flowables)
        self._max_height = max_height

    def wrap(self, aW, aH):
        dims = []
        width, height = _listWrapOn(self._content, aW, self.canv, dims=dims)
        self.height = height
        self.content_dims = dims
        return width, 0xFFFFFF  # force a split

    def split(self, aW, aH):
        if not hasattr(self, "height"):
            self.wrap(aW, aH)
        remaining_space = aH - sum([h for _, h in self.content_dims[:-1]])
        if remaining_space < 0.1 * pdfstyles.PAGE_HEIGHT:
            self._content.insert(0, PageBreak())
            return self._content
        if self.height < aH:
            return self._content

        last = self._content[-1]
        last.keep_together_split = True
        split_last = last.split(aW, remaining_space)

        # if not split_last: last item could not be
        # split and is too big for remaining page
        if not split_last or (split_last and split_last[0].__class__ == PageBreak):
            self._content.insert(0, PageBreak())
        return self._content


class TocEntry(Flowable):
    """Invisible flowable used to build toc.
    FIXME: probably an ActionFlowable should be used."""

    def __init__(self, txt, lvl):
        Flowable.__init__(self)
        self.txt = txt
        self.lvl = lvl

    def draw(self):
        pass


class DummyTable(Flowable):
    def __init__(self, min_widths, max_widths):
        self.min_widths = min_widths
        self.max_widths = max_widths
        Flowable.__init__(self)

    def draw(self):
        return
