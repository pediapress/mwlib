#! /usr/bin/env python

# Copyright (c) 2007, PediaPress GmbH
# See README.txt for additional licensing information.
import logging
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

logger = logging.getLogger(__name__)


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
            canv.translate((self.avail_width - self.width) / 2, 0)
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


class FiguresAndParagraphs(Flowable):
    """takes a list of figures and paragraphs and floats the figures
    next to the paragraphs.
    current limitations:
     * all figures are floated on the same side as the first image
     * the biggest figure-width is used as the text-margin
    """
    def __init__(self, figures, paragraphs, figure_margin=(0,0,0,0), rtl=False):
        self.figures = figures
        self.figure_margin = figure_margin
        self.paragraphs = paragraphs
        self.figAlign = figures[0].align # fixme: all figures will be aligned like the first figure
        if not self.figAlign:
            self.figAlign = 'left' if rtl else 'right'
        for figure in self.figures:
            if self.figAlign == 'left':
                figure.margin = pdfstyles.IMG_MARGINS_FLOAT_LEFT
            else: # default figure alignment is right
                figure.margin = pdfstyles.IMG_MARGINS_FLOAT_RIGHT
        self.wfs = [] #width of figures
        self.hfs = [] # height of figures
        self.rtl = rtl # Flag that indicates if document is set right-to-left

    def _get_vertical_offset(self):
        for p in self.paragraphs:
            if hasattr(p, 'style') and hasattr(p.style, 'spaceBefore'):
                return p.style.spaceBefore
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
            for w, h in img_dims:
                if float(w) < float_width:
                    continue
                changed = True
                new_h = float(h) * float_width / float(w)
                new_w = float_width
                txt = txt.replace('width="%spt"' % w, 'width="%.2fpt"' % new_w)
                txt = txt.replace('height="%spt"' % h, 'height="%.2fpt"' % new_h)
            if changed:
                paragraph._setup(
                    txt,
                    paragraph.style,
                    paragraph.bulletText,
                    None,
                    cleanBlockQuotedText,
                )

    def wrap(self, avail_width, avail_height):
        maxWf = 0
        self.wfs = []
        self.hfs = []
        self.horizontal_rule_offsets = []
        totalHf = self._get_vertical_offset()
        for f in self.figures:
            wf, hf = f.wrap(avail_width, avail_height)
            totalHf += hf
            maxWf = max(maxWf, wf)
            self.wfs.append(wf)
            self.hfs.append(hf)
        self.paraHeights = []
        self._offsets = []
        for p in self.paragraphs:
            if isinstance(p, HRFlowable):
                self.paraHeights.append(1) # fixme: whats the acutal height of a HRFlowable?
                self._offsets.append(0)
                if (totalHf - (sum(self.paraHeights))) > 0: # behave like the associated heading
                    self.horizontal_rule_offsets.append(maxWf)
                else:
                    self.horizontal_rule_offsets.append(0)
                continue
            fullWidth = avail_width - p.style.leftIndent - p.style.rightIndent
            floatWidth = fullWidth - maxWf
            self.resize_inline_image(p, floatWidth)
            nfloatLines = max(0, int((totalHf - (sum(self.paraHeights))) / p.style.leading))
            p.width = 0
            if hasattr(p, 'blPara'):
                del p.blPara
            if hasattr(p, 'style') and p.style.wordWrap == 'CJK':
                p.blPara = p.breakLinesCJK(nfloatLines*[floatWidth] + [fullWidth])
            else:
                p.blPara = p.breakLines(nfloatLines*[floatWidth] + [fullWidth])
            if self.figAlign=='left':
                self._offsets.append([maxWf]*(nfloatLines) + [0])
            autoLeading = p.style.autoLeading if hasattr(p, "style") else ""
            if hasattr(p, 'style') and autoLeading == 'max' and p.blPara.kind == 1:
                pHeight = 0
                for line in p.blPara.lines:
                    pHeight += max(line.ascent - line.descent, p.style.leading) * 1.025 #magic factor! autoLeading==max increases line-height
            else:
                if autoLeading=='max':
                    pHeight = len(p.blPara.lines)*max(p.style.leading, 1.2 * p.style.fontSize)
                    # used to be 1.2 instead of 1.0
                else:
                    pHeight = len(p.blPara.lines)*p.style.leading
            self.paraHeights.append(pHeight + p.style.spaceBefore + p.style.spaceAfter)

        self.width = avail_width
        self.height =  max(sum(self.paraHeights), totalHf)
        return (avail_width, self.height)

    def draw(self):
        canv = self.canv
        canv.saveState()
        vertical_offset = self._get_vertical_offset()
        if self.figAlign == "left":
            horizontal_offsets = [0] * len(self.figures)
        else:
            horizontal_offsets = [self.width - wf for wf in self.wfs]

        for (i,f) in enumerate(self.figures):
            vertical_offset += self.hfs[i]
            f.drawOn(canv, horizontal_offsets[i], self.height - vertical_offset )

        canv.translate(0, self.height)

        for (count,p) in enumerate(self.paragraphs):
            if self.figAlign == 'left':
                p._offsets = self._offsets[count]
                if hasattr(p, 'style') and hasattr(p.style, 'bulletIndent'):
                    if not self.rtl:
                        p.style.bulletIndent += p._offsets[0]
                    else:
                        p.style.bulletIndent -= self.paragraphs[0]._offsets[0] - 34
            if isinstance(p, HRFlowable):
                p.canv = canv
                width_offset = self.horizontal_rule_offsets.pop(0)
                if self.figAlign == 'left':
                    canv.translate(width_offset,0)
                p.wrap(self.width - width_offset , self.height)
                p.draw()
            else:
                canv.translate(0, -p.style.spaceBefore)
                p.canv = canv
                p.draw()
                canv.translate(0, -self.paraHeights[count] + p.style.spaceBefore)

        canv.restoreState()

    def split(self, availWidth, availheight):
        if not hasattr(self,'hfs') or len(self.hfs)==0 or hasattr(self, 'keep_together_split'):
            self.wrap(availWidth, availheight)
        height = self._get_vertical_offset()
        if self.hfs[0] + height > availheight:
            return [PageBreak()] + [FiguresAndParagraphs(self.figures, self.paragraphs, figure_margin=self.figure_margin)]
        fittingFigures = []
        nextFigures = []
        for (i, f) in enumerate(self.figures):
            if (height + self.hfs[i]) < availheight:
                fittingFigures.append(f)
            else:
                nextFigures.append(f)
            height += self.hfs[i]
        fittingParas = []
        nextParas = []
        height = 0
        splittedParagraph=False
        force_split = False
        for (i,p) in enumerate(self.paragraphs):
            # force pagebreak if less than pdfstyles.min_lines_after_heading*line_height available height
            if hasattr(self.paragraphs[i], 'style') and getattr(self.paragraphs[i].style, 'prevent_post_pagebreak', False):
                if len(self.paragraphs) > i+1 and hasattr(self.paragraphs, 'style'):
                    line_height = self.paragraphs[i + 1].style.leading
                else:
                    line_height = pdfstyles.LEADING
                if len(self.paragraphs) > i+1 and (height + self.paraHeights[i] + pdfstyles.MIN_LINES_AFTER_HEADING * line_height) > availheight:
                    force_split = True
            if (height + self.paraHeights[i]) < availheight and not force_split:
                fittingParas.append(p)
            else:
                if splittedParagraph:
                    nextParas.append(p)
                    continue
                paraFrags = p.split(availWidth, availheight - height - p.style.spaceBefore - p.style.spaceAfter - 2 * p.style.leading) # one line-height "safety margin"
                splittedParagraph=True
                if len(paraFrags) == 2:
                    fittingParas.append(paraFrags[0])
                    nextParas.append(paraFrags[1])
                elif len(paraFrags) < 2:
                    nextParas.append(p)
                else: # fixme: not sure if splitting a paragraph can yield more than two elements...
                    pass
            height += self.paraHeights[i]

        if nextFigures:
            if nextParas:
                nextElements = [FiguresAndParagraphs(nextFigures, nextParas, figure_margin=self.figure_margin)]
            else:
                nextElements = nextFigures
        else:
            nextElements = nextParas if nextParas else []
        return [FiguresAndParagraphs(fittingFigures, fittingParas, figure_margin=self.figure_margin)] + nextElements

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
        self._max_height = max_height # 144891,14

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
