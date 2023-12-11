#! /usr/bin/env python

# Copyright (c) 2007, PediaPress GmbH
# See README.txt for additional licensing information.

#################################################################
#
# PLEASE DO NOT EDIT THIS FILE UNLESS YOU KNOW WHAT YOU ARE DOING
#
# If you want to customize the layout of the pdf, do this in
# a separate file customconfig.py
#
#################################################################


import contextlib

from reportlab import rl_config
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm

# used to mark translateable strings:
if "_" not in globals():

    def _(text):
        return text


SERIF_FONT = "FreeSerif"
SANS_FONT = "FreeSans"
MONO_FONT = "FreeMono"
DEFAULT_FONT = "FreeSerif"

rl_config.canvas_basefontname = DEFAULT_FONT


# PAGE CONFIGURATION

PAGE_WIDTH, PAGE_HEIGHT = A4  # roughly: pW= 21*cm pH=29*cm

PAGE_MARGIN_LEFT = 2 * cm
PAGE_MARGIN_RIGHT = 2 * cm
PAGE_MARGIN_TOP = 2 * cm
PAGE_MARGIN_BOTTOM = 2 * cm

HEADER_MARGIN_HOR = 1.5 * cm
HEADER_MARGIN_VERT = 1.5 * cm

FOOTER_MARGIN_HOR = 1.5 * cm
FOOTER_MARGIN_VER = 1.5 * cm

# margins for title page
TITLE_MARGIN_LEFT = PAGE_MARGIN_LEFT
TITLE_MARGIN_RIGHT = PAGE_MARGIN_RIGHT
TITLE_MARGIN_TOP = PAGE_MARGIN_TOP
TITLE_MARGIN_BOTTOM = PAGE_MARGIN_BOTTOM

SHOW_TITLE_PAGE = True
SHOW_TITLE_PAGE_FOOTER = True
SHOW_PAGE_HEADER = True
SHOW_PAGE_FOOTER = True
PAGE_BREAK_AFTER_ARTICLE = False

SHOW_ARTICLE_ATTRIBUTION = True  # Show/Hide article source and contributors
SHOW_ARTICLE_HR = True  # Underline each article header by a horizontal rule
SHOW_WIKI_LICENSE = True

# NOTE: strings can contain reportlab styling tags
# the text needs to be xml excaped.
# more information is available in the reportlab
# user documentation (http://www.reportlab.com/docs/userguide.pdf)
# check the section 6.2 "Paragraph XML Markup Tags"
# since the documenatition is not guaranteed to be up to date,
# you might also want to check the docsting of the
# Paragraph class (reportlab/platypus/paragraph.py --> class Paragraph())
# e.g. the use of inline images is not
# included in the official documenation of reportlab
PAGE_FOOTER = ""

# TITLE PAGE

TITLE_PAGE_IMAGE = ""  # path of an image that is to be displayed on the title page
TITLE_PAGE_IMAGE_SIZE = (
    12 * cm,
    17 * cm,
)  # max. width, height of image, aspect ratio is kept
# position of image relativ to bottom, left corner.
# If component is set to None the image is centered
# It is ensured that the image is not moved out of the page boundaries
TITLE_PAGE_IMAGE_POS = (None, None)

TITLE_PAGE_FOOTER = _(
    "PDF generated using the open source mwlib toolkit. See http://code.pediapress.com/ for more information."
)

# toggle display of PDF generation date in title page footer
SHOW_CREATION_DATE = True
# date format as defined in http://docs.python.org/2/library/time.html#time.strftime
CREATION_DATE_FORMAT = "%a, %d %b %Y %H:%M:%S %Z"
# displayed text. %s will be substituted by the date string defined above
CREATION_DATE_TXT = "PDF generated at: %s"

# if enabled a table of contents is printed at the beginning of the pdf
# note that no TOC is generated if only one article is rendered
RENDER_TOC = True

# TABLE CONFIG

TABLE_OVERFLOW_TOLERANCE = 20  # max width overflow for tables    unit: pt
CELL_PADDING = 3
MIN_ROWS_FOR_BREAK = (
    3  # page breaks before tables are only forced if more than n rows are present
)

# if set to True column widths are extracted from wiki markup if possible
TABLE_WIDTH_FROM_MARKUP = False

# alignment of tables: TA_LEFT | TA_CENTER | TA_RIGHT
TABLE_ALIGN = TA_CENTER

# TREECLEANER CONFIGURATION

TREE_CLEANER_SKIP_METHODS = ["fix_preformatted", "remove_empty_ref_lists"]

# IMAGE CONFIGURATION

# margins for floated images - margins like in html/css:
# (top, right, bottom, left)
IMG_MARGINS_FLOAT_LEFT = (0, 0.4 * cm, 0.7 * cm, 0)  # img that is left aligned
IMG_MARGINS_FLOAT_RIGHT = (0, 0, 0.7 * cm, 0.4 * cm)  # ...
IMG_MARGINS_FLOAT = (0.2 * cm, 0.2 * cm, 0.2 * cm, 0.2 * cm)  # any other alignment

IMG_DEFAULT_THUMB_WIDTH = 180
IMG_MAX_THUMG_WIDTH = 0.6  # fraction of print width for floated images
IMG_MAX_THUMG_HEIGHT = 0.45
IMG_MIN_RES = 75
IMG_INLINE_SCALE_FACTOR = 0.7  # factor by which inline images are scaled.
PRINT_WIDTH_PX = 540  # 540px are assumed to be the equivalent for a full print width

IMG_BORDER_COLOR = (0.75, 0.75, 0.75)

LINK_IMAGES = True

# TEXT CONFIGURATION
FONT_SIZE = 10
LEADING = 15
TEXT_ALIGN = TA_JUSTIFY  # default alignment of text outside of tables TA_LEFT, TA_JUSTIFY, TA_RIGHT, TA_CENTER are valid
TABLE_TEXT_ALIGN = TA_LEFT  # ... inside of tables
MIN_LINES_AFTER_HEADING = 5

SMALL_FONT_SIZE = 8
SMALL_LEADING = 12

BIG_FONT_SIZE = 12
BIG_LEADING = 17

PARA_LEFT_INDENT = 25  # indentation of paragraphs...
PARA_RIGHT_INDENT = 25  # indentation of paragraphs...
LIST_LEFT_INDENT = 12  # indentation of lists per level

TABSIZE = 6

SOURCE_MAX_LINE_LEN = (
    72  # if printing a source node, the maximum number of chars in one line
)

NO_FLOAT_MATH_LEN = 150

MAX_MATH_WIDTH = 2500
MAX_MATH_HEIGHT = 2500
# set to CJK if a PDF is rendered mainly using chinese,
# japanese or korean glyphs
WORD_WRAP = None

MIN_PREFORMATTED_SIZE = 5


CHAPTER_RULE_COLOR = colors.black
# misc options

LIST_ITEM_STYLE = "\u2022"

URL_BLACKLIST = ["http://toolserver.org"]

# URLs in tables are put in the reference section if
# url_ref_in_table = True and url is longer than url_ref_len
URL_REF_IN_TABLE = True
URL_REF_LEN = 30


class BaseStyle(ParagraphStyle):
    def __init__(self, name, parent=None, **kw):
        ParagraphStyle.__init__(self, name=name, parent=parent, **kw)
        self.fontName = SERIF_FONT
        self.fontSize = FONT_SIZE
        self.leading = LEADING
        self.autoLeading = "max"
        self.leftIndent = 0
        self.rightIndent = 0
        self.firstLineIndent = 0
        self.alignment = TEXT_ALIGN
        self.spaceBefore = 3
        self.spaceAfter = 0
        self.bulletFontName = SERIF_FONT
        self.bulletFontSize = FONT_SIZE
        self.bulletIndent = 0
        self.textColor = colors.black
        self.backColor = None
        self.wordWrap = None
        self.textTransform = None
        self.strikeWidth = 1
        self.underlineWidth = 1


def get_font_size(relsize, mode):
    if relsize == "small":
        font_size = SMALL_FONT_SIZE - 1
    elif relsize == "big":
        font_size = SMALL_FONT_SIZE + 1
    elif mode in ["footer", "figure", "center", "references", "articlefoot"]:
        font_size = SMALL_FONT_SIZE
    elif mode == "booktitle":
        font_size = 36
    elif mode == "booksubtitle":
        font_size = 24
    elif mode == "License" or mode == "licenselist":
        font_size = 5
    elif mode == "toc_group":
        font_size = 18
    elif mode == "toc_chapter":
        font_size = 14
    elif mode == "toc_article":
        font_size = 10
    else:
        font_size = None
    return font_size


def get_leading(mode):
    if mode in ["footer", "figure", "center", "references", "articlefoot", "License", "licenselist"]:
        leading = SMALL_LEADING
    elif mode == "booktitle":
        leading = 40
    elif mode == "booksubtitle":
        leading = 30
    elif mode == "toc_group":
        leading = 22
    elif mode == "toc_chapter":
        leading = 18
    elif mode == "toc_article":
        leading = 12
    else:
        leading = None
    return leading


def get_alignment(text_align, mode):
    if text_align == "right":
        alignment = TA_RIGHT
    elif text_align == "center" or mode in ["footer", "figure", "center"]:
        alignment = TA_CENTER
    elif mode in ["references", "articlefoot", "source", "preformatted", "list", "attribution", "img_attribution"]:
        alignment = TA_LEFT
    else:
        alignment = TA_LEFT
    return alignment


def set_conditional_font_and_leading(in_table, mode, relsize, font_size, leading, style):
    if (
        in_table
        or mode in ["footer", "figure"]
        or (mode == "preformatted" and relsize == "small")
    ):
        style.fontSize = SMALL_FONT_SIZE
        style.bulletFontSize = SMALL_FONT_SIZE
        style.leading = SMALL_LEADING
        if font_size is not None:
            style.fontSize = font_size
        if leading is not None:
            style.leading = leading


def text_style(mode="p", indent_lvl=0, in_table=0,
               relsize="normal", text_align=None):
    """
    mode: p (normal paragraph), blockquote, center (centered paragraph),
    footer, figure (figure caption text),
          preformatted, list, license, licenselist,
          box, references, articlefoot
    relsize: relative text size: small, normal, big  (currently only
                used for preformatted nodes
    indent_lvl: level of indentation in lists or indented paragraphs
    in_table: 0 - outside table
              1 or above - inside table (nesting level of table)
    text_align: left, center, right, justify
    """

    if not text_align:
        text_align = "left"

    font_size = get_font_size(relsize, mode)
    leading = get_leading(mode)
    alignment = get_alignment(text_align, mode)

    style = BaseStyle(
        name="text_style_%s_indent_%d_table_%d_size_%s"
        % (mode, indent_lvl, in_table, relsize)
    )
    style.flowable = True  # needed for "flowing" paragraphs around figures

    if WORD_WRAP in ["CJK", "RTL"] and mode not in ["preformatted", "source"]:
        style.wordWrap = WORD_WRAP

    if in_table > 0:
        style.alignment = TABLE_TEXT_ALIGN
    style.alignment = alignment

    set_conditional_font_and_leading(in_table, mode, relsize, font_size, leading, style)

    if mode == "blockquote":
        style.rightIndent = PARA_RIGHT_INDENT
        indent_lvl += 1

    if mode in ['box', 'source', 'preformatted']:
        style.backColor = "#eeeeee"
        style.borderPadding = (
            3  # borderPadding is not calculated onto the box dimensions.
        )
        style.spaceBefore = 6  # therefore spaceBefore = 3 + borderPadding
        style.spaceAfter = (
            9  # add an extra 3 to spaceAfter, b/c spacing seems to small otherwise
        )

    if mode in ['source', 'preformatted']:
        style.fontName = MONO_FONT
        style.flowable = False

    if mode in ['list', 'references']:
        style.spaceBefore = 0
        style.bulletIndent = LIST_LEFT_INDENT * max(0, indent_lvl - 1)
        style.leftIndent = LIST_LEFT_INDENT * indent_lvl
    else:
        style.leftIndent = indent_lvl * PARA_LEFT_INDENT

    if mode in ["attribution", "img_attribution"]:
        style.fontSize = 6
        style.leading = 8
        style.spaceBefore = 6

    if mode == "img_attribution":
        style.spaceBefore = 2

    return style


TABLE_STYLE = {"spaceBefore": 0.25 * cm, "spaceAfter": 0.25 * cm}


class BaseHeadingStyle(ParagraphStyle):
    def __init__(self, name, parent=None, **kw):
        ParagraphStyle.__init__(self, name=name, parent=parent, **kw)
        self.fontName = SERIF_FONT
        self.fontSize = BIG_FONT_SIZE
        self.leading = LEADING
        self.autoLeading = "max"
        self.leftIndent = 0
        self.rightIndent = 0
        self.firstLineIndent = 0
        self.alignment = TA_LEFT
        self.spaceBefore = 12
        self.spaceAfter = 6
        self.bulletFontName = SERIF_FONT
        self.bulletFontSize = BIG_FONT_SIZE
        self.bulletIndent = 0
        self.textColor = colors.black
        self.backcolor = None
        self.wordWrap = None
        self.textTransform = None


def heading_style(mode="Chapter", lvl=1, text_align=None):
    style = BaseHeadingStyle(name="heading_style_%s_%d" % (mode, lvl))

    if WORD_WRAP == "RTL":
        style.wordWrap = "RTL"
        if not text_align:
            style.alignment = TA_RIGHT

    if mode == "Chapter":
        style.fontSize = 26
        style.leading = 30
        style.alignment = TA_CENTER
    elif mode == "article":
        style.fontSize = 22
        style.leading = 26
        style.spaceBefore = 20
        style.spaceAfter = 2
    elif mode == "section":
        lvl = max(min(5, lvl), 1)
        style.fontSize = 18 - (lvl - 1) * 2
        style.leading = style.fontSize + max(
            2, min(int(style.fontSize / 5), 3)
        )  # magic: increase in leading is between 2 and 3 depending on fontsize...
        style.spaceBefore = min(style.leading, 20)
        if lvl > 1:  # needed for "flowing" paragraphs around figures
            style.flowable = True
    elif mode == "tablecaption":
        style.fontSize = 12
        style.leading = 16
        style.alignment = TA_CENTER
        style.flowable = False
        style.spaceAfter = 0
    elif mode == "License":
        style.fontSize = 7
        style.leading = 5
        style.spaceAfter = 0
        style.spaceBefore = 2

    if text_align == "left":
        style.alignment = TA_LEFT
    elif text_align == "center":
        style.alignment = TA_CENTER
    elif text_align == "right":
        style.alignment = TA_RIGHT
    elif text_align == "justify":
        style.alignment = TA_JUSTIFY

    style.prevent_post_pagebreak = True
    return style


# import custom configuration to override configuration values
# if doing so, you need to be careful not to break things...
with contextlib.suppress(ImportError):
    from customconfig import *


PRINT_WIDTH = PAGE_WIDTH - PAGE_MARGIN_LEFT - PAGE_MARGIN_RIGHT
PRINT_HEIGHT = PAGE_HEIGHT - PAGE_MARGIN_TOP - PAGE_MARGIN_BOTTOM

ARTICLE_START_MIN_SPACE = (
    0.5 * PRINT_HEIGHT
)  # if less space is available on the current page a page break is inserted
ARTICLE_START_MIN_SPACE_INFOBOX = (
    0.9 * PRINT_HEIGHT
)  # as above. but if the article starts with an infobox the required space should be higher

MIN_TABLE_SPACE = (
    PRINT_HEIGHT / 4
)  # if less space is available, a page break will be inserted before the table
