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

from mwlib.rl import pdfstyles


class Figure(Flowable):
    def __init__(
        self,
        imgFile,
        captionTxt,
        captionStyle,
        imgWidth=None,
        imgHeight=None,
        margin=(0, 0, 0, 0),
        padding=(0, 0, 0, 0),
        align=None,
        borderColor=(0.75, 0.75, 0.75),
        no_mask=False,
        url=None,
    ):
        imgFile = imgFile
        self.imgPath = imgFile
        # workaround for http://code.pediapress.com/wiki/ticket/324
        # see http://two.pairlist.net/pipermail/reportlab-users/2008-October/007526.html
        if no_mask:
            self.i = Image(imgFile, width=imgWidth,
                           height=imgHeight, mask=None)
        else:
            self.i = Image(imgFile, width=imgWidth, height=imgHeight)
        self.imgWidth = imgWidth
        self.imgHeight = imgHeight
        self.c = Paragraph(captionTxt, style=captionStyle)
        self.margin = margin  # 4-tuple. margins in order: top, right, bottom, left
        self.padding = padding  # same as above
        self.borderColor = borderColor
        self.align = align
        self.cs = captionStyle
        self.captionTxt = captionTxt
        self.avail_width = None
        self.avail_height = None
        self.url = url

    def draw(self):
        canv = self.canv
        if self.align == "center":
            canv.translate((self.avail_width - self.width / 2), 0)
        canv.saveState()
        canv.setStrokeColor(Color(self.borderColor[0], self.borderColor[1],
                                  self.borderColor[2]))
        canv.rect(self.margin[3], self.margin[2], self.boxWidth,
                  self.boxHeight)
        canv.restoreState()
        canv.translate(self.margin[3] + self.padding[3],
                       self.margin[2] + self.padding[2] - 2)
        self.c.canv = canv
        self.c.draw()
        canv.translate(
            (self.boxWidth - self.padding[1] - self.padding[3] - self.i.drawWidth) / 2,
            self.captionHeight + 2,
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
            canv.linkURL(clean_url, (0, 0, self.imgWidth, self.imgHeight),
                         relative=1, thickness=0)

    def wrap(self, avail_width, avail_height):
        self.avail_width = avail_width
        self.avail_height = avail_height
        content_width = max(self.i.drawWidth, self.c.wrap(self.i.drawWidth,
                                                         avail_height)[0])
        self.boxWidth = content_width + self.padding[1] + self.padding[3]
        (self.captionWidth, self.captionHeight) = self.c.wrap(content_width,
                                                              avail_height)
        self.captionHeight += self.cs.spaceBefore + self.cs.spaceAfter
        self.boxHeight = self.i.drawHeight + self.captionHeight + self.padding[0] + self.padding[2]
        self.width = self.boxWidth + self.margin[1] + self.margin[3]
        self.height = self.boxHeight + self.margin[0] + self.margin[2]
        return (self.width, self.height)


class FiguresAndParagraphs(Flowable):
    """takes a list of figures and paragraphs and floats the figures
    next to the paragraphs.
    current limitations:
     * all figures are floated on the same side as the first image
     * the biggest figure-width is used as the text-margin
    """

    def __init__(self, figures, paragraphs,
                 figure_margin=(0, 0, 0, 0), rtl=False):
        self.fs = figures
        self.figure_margin = figure_margin
        self.ps = paragraphs
        self.figAlign = figures[
            0
        ].align  # fixme: all figures will be aligned like the first figure
        if not self.figAlign:
            self.figAlign = "left" if rtl else "right"
        for f in self.fs:
            if self.figAlign == "left":
                f.margin = pdfstyles.IMG_MARGINS_FLOAT_LEFT
            else:  # default figure alignment is right
                f.margin = pdfstyles.IMG_MARGINS_FLOAT_RIGHT
        self.wfs = []  # width of figures
        self.hfs = []  # height of figures
        self.rtl = rtl  # Flag that indicates if document is set right-to-left

    def _getVOffset(self):
        for p in self.ps:
            if hasattr(p, "style") and hasattr(p.style, "spaceBefore"):
                return p.style.spaceBefore
        return 0

    def resizeInlineImage(self, p, float_width):
        if p.text is None:
            return
        img_dims = re.findall('<img.*?width="([0-9.]+)pt".*?height="([0-9.]+)pt".*?/>', p.text)
        if img_dims:
            txt = p.text
            changed = False
            for w, h in img_dims:
                if float(w) < float_width:
                    continue
                changed = True
                new_h = float(h) * float_width / float(w)
                new_w = float_width
                txt = txt.replace('width="%spt"' % w, 'width="%.2fpt"' % new_w)
                txt = txt.replace('height="%spt"' % h,
                                  'height="%.2fpt"' % new_h)
            if changed:
                p._setup(txt, p.style,
                         p.bulletText, None, cleanBlockQuotedText)

    def wrap(self, avail_width, avail_height):
        maxWf = 0
        self.wfs = []
        self.hfs = []
        self.horizontalRuleOffsets = []
        total_hf = self._getVOffset()
        for f in self.fs:
            wf, hf = f.wrap(avail_width, avail_height)
            total_hf += hf
            maxWf = max(maxWf, wf)
            self.wfs.append(wf)
            self.hfs.append(hf)
        self.paraHeights = []
        self._offsets = []
        for p in self.ps:
            if isinstance(p, HRFlowable):
                self.paraHeights.append(1)  # fixme: whats the acutal height of a HRFlowable?
                self._offsets.append(0)
                if (total_hf - (sum(self.paraHeights))) > 0:  # behave like the associated heading
                    self.horizontalRuleOffsets.append(maxWf)
                else:
                    self.horizontalRuleOffsets.append(0)
                continue
            full_width = avail_width - p.style.leftIndent - p.style.rightIndent
            float_width = full_width - maxWf
            self.resizeInlineImage(p, float_width)
            nfloatLines = max(0,
                              int((total_hf - (sum(self.paraHeights))) / p.style.leading))
            p.width = 0
            if hasattr(p, "blPara"):
                del p.blPara
            if hasattr(p, "style") and p.style.wordWrap == "CJK":
                p.blPara = p.breakLinesCJK(nfloatLines * [float_width] + [full_width])
            else:
                p.blPara = p.breakLines(nfloatLines * [float_width] + [full_width])
            if self.figAlign == "left":
                self._offsets.append([maxWf] * (nfloatLines) + [0])
            autoLeading = getattr(p.style,
                                  "autoLeading") if hasattr(p, "style") else ""
            if hasattr(p, "style") and autoLeading == "max" and p.blPara.kind == 1:
                pHeight = 0
                for line in p.blPara.lines:
                    pHeight += (
                        max(line.ascent - line.descent,
                            p.style.leading) * 1.025
                    )  # magic factor! autoLeading==max increases line-height
            else:
                if autoLeading == "max":
                    pHeight = len(p.blPara.lines) * max(
                        p.style.leading, 1.2 * p.style.fontSize
                    )  # used to be 1.2 instead of 1.0
                else:
                    pHeight = len(p.blPara.lines) * p.style.leading
            self.paraHeights.append(pHeight + p.style.spaceBefore + p.style.spaceAfter)

        self.width = avail_width
        self.height = max(sum(self.paraHeights), total_hf)
        return (avail_width, self.height)

    def draw(self):
        canv = self.canv
        canv.saveState()
        vertical_offset = self._getVOffset()
        if self.figAlign == "left":
            horizontal_offsets = [0] * len(self.fs)
        else:
            horizontal_offsets = [self.width - wf for wf in self.wfs]

        for (i, f) in enumerate(self.fs):
            vertical_offset += self.hfs[i]
            f.drawOn(canv, horizontal_offsets[i],
                     self.height - vertical_offset)

        canv.translate(0, self.height)

        for (count, p) in enumerate(self.ps):
            if self.figAlign == "left":
                p._offsets = self._offsets[count]
                if hasattr(p, "style") and hasattr(p.style, "bulletIndent"):
                    if not self.rtl:
                        p.style.bulletIndent += p._offsets[0]
                    else:
                        p.style.bulletIndent -= self.ps[0]._offsets[0] - 34
            if isinstance(p, HRFlowable):
                p.canv = canv
                widthOffset = self.horizontalRuleOffsets.pop(0)
                if self.figAlign == "left":
                    canv.translate(widthOffset, 0)
                p.wrap(self.width - widthOffset, self.height)
                p.draw()
            else:
                canv.translate(0, -p.style.spaceBefore)
                p.canv = canv
                p.draw()
                canv.translate(0,
                               -self.paraHeights[count] + p.style.spaceBefore)

        canv.restoreState()

    def split(self, avail_width, avail_height):
        if not hasattr(self,
                       "hfs") or len(
                                    self.hfs) == 0 or hasattr(self,
                                                              "keep_together_split"):
            self.wrap(avail_width, avail_height)
        height = self._getVOffset()
        if self.hfs[0] + height > avail_height:
            return [PageBreak()] + [
                FiguresAndParagraphs(self.fs, self.ps,
                                     figure_margin=self.figure_margin)
            ]
        fitting_figures = []
        next_figures = []
        for (i, f) in enumerate(self.fs):
            if (height + self.hfs[i]) < avail_height:
                fitting_figures.append(f)
            else:
                next_figures.append(f)
            height += self.hfs[i]
        fitting_paras = []
        next_paras = []
        height = 0
        splitted_paragraph = False
        force_split = False
        for (i, p) in enumerate(self.ps):
            # force pagebreak if less than
            # pdfstyles.min_lines_after_heading*line_height available height
            if hasattr(self.ps[i], "style") and getattr(
                self.ps[i].style, "prevent_post_pagebreak", False
            ):
                if len(self.ps) > i + 1 and hasattr(self.ps, "style"):
                    line_height = self.ps[i + 1].style.leading
                else:
                    line_height = pdfstyles.LEADING
                if (
                    len(self.ps) > i + 1
                    and (
                        height
                        + self.paraHeights[i]
                        + pdfstyles.MIN_LINES_AFTER_HEADING * line_height
                    )
                    > avail_height
                ):
                    force_split = True
            if (height + self.paraHeights[i]) < avail_height and not force_split:
                fitting_paras.append(p)
            else:
                if splitted_paragraph:
                    next_paras.append(p)
                    continue
                para_frags = p.split(
                    avail_width,
                    avail_height
                    - height
                    - p.style.spaceBefore
                    - p.style.spaceAfter
                    - 2 * p.style.leading,
                )  # one line-height "safety margin"
                splitted_paragraph = True
                if len(para_frags) == 2:
                    fitting_paras.append(para_frags[0])
                    next_paras.append(para_frags[1])
                elif len(para_frags) < 2:
                    next_paras.append(p)
                else:  # fixme: not sure if splitting a paragraph can yield more than two elements...
                    pass
            height += self.paraHeights[i]

        if next_figures:
            if next_paras:
                next_elements = [
                    FiguresAndParagraphs(next_figures, next_paras,
                                         figure_margin=self.figure_margin)
                ]
            else:
                next_elements = next_figures
        else:
            next_elements = next_paras if next_paras else []
        return [
            FiguresAndParagraphs(fitting_figures, fitting_paras,
                                 figure_margin=self.figure_margin)
        ] + next_elements


class PreformattedBox(Preformatted):
    def __init__(self, text, style, margin=4, padding=4,
                 borderwidth=0.1, **kwargs):
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

        lines_that_fit = int((avail_height - self.padding - self.margin) * 1.0 / self.style.leading)

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
