#! /usr/bin/env python

# Copyright (c) 2007, PediaPress GmbH
# See README.txt for additional licensing information.


import os
import re

from reportlab.lib.fonts import addMapping
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont

from mwlib import fonts
from mwlib.writer.fontswitcher import FontSwitcher

font_paths = [os.path.dirname(fonts.__file__),
              os.path.expanduser("~/mwlibfonts/")]

# from the fonts defined below only FreeFont is part of the mwlib packet
# the other fonts can be obtained by installing the following debian packets:
# aptitude install ttf-indic-fonts ttf-unfonts ttf-farsiweb
# ttf-arphic-uming ttf-gfs-artemisia ttf-sil-ezra ttf-thai-arundina
# linux-libertine
# after that the fonts need to be moved or symlinked to one of the font_paths
fonts = [
    {
        "name": "FreeSerif",
        "code_points": [
            "Basic Latin",
            "Latin-1 Supplement",
            "Latin Extended-A",
            "Latin Extended-B",
            "Latin Extended Additional",
            (64256, 64262),
            "Cyrillic",
            "Cyrillic Supplement",
            "Cyrillic Extended-B",
            "Greek Extended",
            "Greek and Coptic",
            "Geometric Shapes",
            "Hebrew",
            "Alphabetic Presentation Forms",
            "Miscellaneous Symbols",
            "Mathematical Alphanumeric Symbols",
        ],
        "xl_scripts": ["Latin", "Cyrillic", "Greek", "Coptic", "Hebrew"],
        "file_names": [
            "freefont/FreeSerif.ttf",
            "freefont/FreeSerifBold.ttf",
            "freefont/FreeSerifItalic.ttf",
            "freefont/FreeSerifBoldItalic.ttf",
        ],
    },
    {
        "name": "FreeSans",
        "code_points": [
            "IPA Extensions",
            "Spacing Modifier Letters",
            "Combining Diacritical Marks",
            "Armenian",
            "NKo",
            "Lao",
            "Georgian",
            "Unified Canadian Aboriginal Syllabics",
            "Ogham",
            "Phonetic Extensions",
            "Phonetic Extensions Supplement",
            "Combining Diacritical Marks Supplement",
            "General Punctuation",
            "Superscripts and Subscripts",
            "Currency Symbols",
            "Combining Diacritical Marks for Symbols",
            "Letterlike Symbols",
            "Number Forms",
            "Arrows",
            "Mathematical Operators",
            "Miscellaneous Technical",
            "Control Pictures",
            "Enclosed Alphanumerics",
            "Block Elements",
            "Dingbats",
            "Miscellaneous Mathematical Symbols-A",
            "Supplemental Arrows-A",
            "Braille Patterns",
            "Miscellaneous Mathematical Symbols-B",
            "Supplemental Mathematical Operators",
            "Miscellaneous Symbols and Arrows",
            "Latin Extended-C",
            "Tifinagh",
            "Supplemental Punctuation",
            "Yijing Hexagram Symbols",
            "Modifier Tone Letters",
            "Latin Extended-D",
            "Variation Selectors",
            "Combining Half Marks",
            "Specials",
            "Tai Xuan Jing Symbols",
            "Mathematical Alphanumeric Symbols",
            "Syriac",
        ],
        "file_names": [
            "freefont/FreeSans.ttf",
            "freefont/FreeSansBold.ttf",
            "freefont/FreeSansOblique.ttf",
            "freefont/FreeSansBoldOblique.ttf",
        ],
    },
    {
        "name": "FreeMono",
        "code_points": ["Box Drawing"],  # also used for code/source/etc.
        "xl_scripts": [],
        "file_names": [
            "freefont/FreeMono.ttf",
            "freefont/FreeMonoBold.ttf",
            "freefont/FreeMonoOblique.ttf",
            "freefont/FreeMonoBoldOblique.ttf",
        ],
    },
    {
        "name": "STSong-Light",  # built in Adobe font - only used if AR PL UMing HK is not found
        "code_points": [
            "Bopomofo",
            "CJK Radicals Supplement",
            "Bopomofo Extended",
            "CJK Unified Ideographs Extension A",
            "CJK Unified Ideographs",
            "Small Form Variants",
        ],
        "type": "cid",
        "cjk": True,
    },
    {
        "name": "HYSMyeongJo-Medium",  # built in Adobe font - only used if AR PL UMing HK is not found
        "code_points": [
            "CJK Compatibility Ideographs",
            "Hangul Compatibility Jamo",
            "Hangul Syllables",
        ],
        "type": "cid",
        "cjk": True,
    },
    {
        "name": "AR PL UMing HK",
        "code_points": [
            "CJK Unified Ideographs",
            "CJK Strokes",
            "CJK Unified Ideographs Extension A",
            "Halfwidth and full_width Forms",
            "CJK Compatibility Ideographs",
            "Small Form Variants",
            "Low Surrogates",
            "CJK Radicals Supplement",
            "Hiragana",
            "Katakana",
            "Bopomofo",
            "Bopomofo Extended",
            "CJK Symbols and Punctuation",
        ],
        "file_names": ["arphic/uming.ttc"],
        "cjk": True,
    },
    {
        "name": "Nazli",
        "code_points": [
            "Arabic Presentation Forms-A",
            "Arabic",
            "Arabic Presentation Forms-B",
            "Arabic Supplement",
        ],
        "file_names": [
            "customnazli/nazli.ttf",
            "customnazli/nazlib.ttf",
            "customnazli/nazli-italic.ttf",
            "customnazli/nazlib-italic.ttf",
        ],
    },
    {
        "name": "UnBatang",
        "code_points": ["Hangul Syllables", "Hangul Jamo", "Hangul Compatibility Jamo"],
        "file_names": ["unfonts/UnBatang.ttf"],
    },
    {
        "name": "Arundina Serif",
        "code_points": ["Thai"],
        "file_names": [
            "ttf-thai-arundina/ArundinaSans.ttf",
            "ttf-thai-arundina/ArundinaSans-Bold.ttf",
            "ttf-thai-arundina/ArundinaSans-Oblique.ttf",
            "ttf-thai-arundina/ArundinaSans-BoldOblique.ttf",
        ],
    },
    {
        "name": "Lohit Telugu",
        "code_points": ["Telugu"],
        "file_names": ["ttf-telugu-fonts/lohit_te.ttf"],
    },
    {
        "name": "Sarai",
        "code_points": ["Devanagari"],
        "file_names": ["ttf-devanagari-fonts/Sarai_07.ttf"],
    },
    {
        "name": "Gujarati",
        "code_points": ["Gujarati"],
        "file_names": ["ttf-indic-fonts-core/lohit_gu.ttf"],
    },
    {
        "name": "Lohit Punjabi",
        "code_points": ["Gurmukhi"],
        "file_names": ["ttf-indic-fonts-core/lohit_pa.ttf"],
    },
    {
        "name": "Lohit Oriya",
        "code_points": ["Oriya"],
        "file_names": ["ttf-oriya-fonts/lohit_or.ttf"],
    },
    {
        "name": "AnjaliOldLipi",
        "code_points": ["Malayalam"],
        "file_names": ["ttf-malayalam-fonts/AnjaliOldLipi.ttf"],
    },
    {
        "name": "Kedage",
        "code_points": ["Kannada"],
        "file_names": [
            "ttf-kannada-fonts/Kedage-n.ttf",
            "ttf-kannada-fonts/Kedage-b.ttf",
            "ttf-kannada-fonts/Kedage-i.ttf",
            "ttf-kannada-fonts/Kedage-t.ttf",
        ],
    },
    {
        "name": "LikhanNormal",
        "code_points": ["Bengali"],
        "file_names": ["ttf-bengali-fonts/LikhanNormal.ttf"],
    },
    {
        "name": "Lohit Tamil",
        "code_points": ["Tamil"],
        "file_names": ["ttf-indic-fonts-core/lohit_ta.ttf"],
    },
    {
        "name": "Khmer",
        "code_points": ["Khmer", "Khmer Symbols"],
        "file_names": ["ttf-khmeros-core/KhmerOS.ttf"],
    },
]

try:
    from customconfig import fonts

    print("using font definition from customconfig.py".upper())
except ImportError:
    pass


class RLFontSwitcher(FontSwitcher):
    warn_on_missing_fonts = True

    def __init__(self):
        FontSwitcher.__init__(self)
        self.font_paths = font_paths
        self.force_font = None
        self.hypenation_pattern = re.compile(r"(/|\.|\+|-|_|\?)(\S)")

    def register_font_def_list(self, font_list):
        missing_fonts = []
        for font in font_list:
            if not font["name"]:
                continue
            if not self.font_installed(font):
                missing_fonts.append(repr(font["name"]))
                continue
            self.register_font(font["name"],
                               code_points=font.get("code_points"))
            if font.get("cjk", False):
                self.cjk_fonts.append(font["name"])
        if RLFontSwitcher.warn_on_missing_fonts and missing_fonts:
            print("MISSING FONTS:", ",".join(missing_fonts))
            RLFontSwitcher.warn_on_missing_fonts = False

    def fake_hyphenate(self, font_list):
        zws = '<font fontSize="1"> </font>'
        res = []
        for txt, font in font_list:
            txt = re.sub(self.hypenation_pattern, r"\g<1>%s\g<2>" % zws, txt)
            res.append((txt, font))
        return res

    def insert_zws(self, font_list):
        zws = '<font fontSize="1"> </font>'
        lst = []
        for txt, font in font_list:
            new_txt = zws.join(c for c in txt) if font in self.cjk_fonts else txt
            lst.append((new_txt, font))
        return lst

    def fontify_text(self, txt, break_long=False):
        if self.force_font:
            return f'<font name="{self.force_font}">{txt}</font>'
        font_list = self.get_font_list(txt)
        if self.space_cjk:
            font_list, cjk = font_list
            if cjk:
                font_list = self.insert_zws(font_list)
        if break_long:
            font_list = self.fake_hyphenate(font_list)

        res = []
        for txt, font in font_list:
            if font != self.default_font:
                res.append(f'<font name="{font}">{txt}</font>')
            else:
                res.append(txt)

        return "".join(res)

    def getfont_for_script(self, script):
        for font_def in fonts:
            if script in (
                s.lower() for s in font_def["code_points"] if isinstance(s,
                                                                         str)
            ) and self.font_installed(font_def):
                return font_def["name"]
        return None

    def font_installed(self, font_def):
        if font_def.get("type") == "cid":
            return True
        return all(
            self.get_abs_font_path(file_name) for file_name in font_def.get("file_names")
        )

    def get_abs_font_path(self, file_name):
        for base_dir in self.font_paths:
            full_path = os.path.join(base_dir, file_name)
            if os.path.exists(full_path):
                return full_path
        return None

    def register_reportlab_fonts(self, font_list):
        font_variants = ["", "bold", "italic", "bolditalic"]
        for font in font_list:
            if not font.get("name"):
                continue
            if font.get("type") == "cid":
                pdfmetrics.registerFont(UnicodeCIDFont(font["name"]))
            else:
                for i, font_variant in enumerate(font_variants):
                    if i == len(font.get("file_names")) or not self.font_installed(font):
                        break
                    full_font_name = font["name"] + font_variant
                    pdfmetrics.registerFont(
                        TTFont(
                            full_font_name,
                            self.get_abs_font_path(font.get("file_names")[i]),
                        )
                    )
                    italic = font_variant in ["italic", "bolditalic"]
                    bold = font_variant in ["bold", "bolditalic"]
                    addMapping(font["name"], bold, italic, full_font_name)
