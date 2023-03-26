#! /usr/bin/env python
#! -*- coding:utf-8 -*-

# Copyright (c) 2007, PediaPress GmbH
# See README.txt for additional licensing information.

from xml.sax.saxutils import escape as xmlescape

from mwlib.writer.formatter import Formatter
from mwlib.rl import pdfstyles


class RLFormatter(Formatter):
    def __init__(self, font_switcher=None, output_encoding=None):
        Formatter.__init__(self, font_switcher=font_switcher, output_encoding=output_encoding)

    def register_render_styles(self):
        return [
            ("emphasized_style", "<i>", "</i>", None),
            ("strong_style", "<b>", "</b>", None),
            ("small_style", '<font size="%d">' % pdfstyles.small_font_size, "</font>", None),
            ("big_style", '<font size="%s">' % pdfstyles.big_font_size, "</font>", None),
            ("sub_style", "<sub>", "</sub>", None),
            ("sup_style", "<sup>", "</sup>", None),
            ("teletype_style", '<font fontName="%s">' % pdfstyles.mono_font, "</font>", None),
            ("strike_style", "<strike>", "</strike>", None),
            ("underline_style", "<u>", "</u>", None),
            ("overline_style", "", "", None),
            ("fontsize_style", '<font size="%.2f">', "</font>", "abs_font_size"),
            ("color_style", '<font color="%s">', "</font>", "color_str"),
        ]

    def escape_text(self, txt):
        return xmlescape(txt)

    def escape_and_hyphenate_text(self, txt):  # FIXME: is that what we want?
        return xmlescape(txt)

    @property
    def abs_font_size(self):
        return pdfstyles.font_size * self.rel_font_size

    @property
    def color_str(self):
        return "#" + "".join(["%2.2x" % int(c * 255) for c in self.color_style])
