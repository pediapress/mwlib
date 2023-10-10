#! /usr/bin/env python

# Copyright (c) 2007, PediaPress GmbH
# See README.rst for additional licensing information.


from mwlib.tree import advtree
from mwlib.writer import styleutils


class Formatter:
    """store the current formatting state"""

    fontsize_style = None

    css_style_map = {
        "font-style": {
            "italic": [("emphasized_style", "change")],
            "oblique": [("emphasized_style", "change")],
            "normal": [("emphasized_style", "reset")],
        },
        "font-family": {
            "Courier": [("teletype_style", "change")],
        },
        "font-weight": {
            "bold": [("strong_style", "change")],
            # bolder and bold are treated the same
            "bolder": [("strong_style", "change")],
            "normal": [("strong_style", "reset")],
            # treat lighter as normal
            "lighter": [("strong_style", "reset")],
        },
        "text-decoration": {
            "overline": [
                ("overline_style", "change"),
                ("underline_style", "reset"),
                ("strike_style", "reset"),
            ],
            "underline": [
                ("underline_style", "change"),
                ("overline_style", "reset"),
                ("strike_style", "reset"),
            ],
            "line-through": [
                ("strike_style", "change"),
                ("underline_style", "reset"),
                ("overline_style", "reset"),
            ],
        },
        "color": {"*": ("color_style", styleutils.rgb_color_from_node)},
    }

    def __init__(self, font_switcher=None,
                 output_encoding=None, word_split_len=20):
        self.font_switcher = font_switcher

        self.default_font = "DejaVuSerif"
        self.default_mono_font = "DejaVuSansMono"

        self.output_encoding = output_encoding

        self.render_styles = self.register_render_styles()
        self.node_styles = self.register_node_styles()

        for style, start_style, end_style, start_attr in self.render_styles:
            setattr(self, style, 0)

        self.source_mode = 0
        self.pre_mode = 0
        self.index_mode = 0
        self.gallery_mode = 0
        self.footnote_mode = 0
        self.minimize_space_mode = 0  # used for tables if we try to safe space

        self.section_title_mode = False
        self.attribution_mode = True
        self.last_font = None
        self.table_nesting = 0
        self.rel_font_size = 1

        self.grouping_chars = ("", "")
        self.word_split_len = word_split_len

    def register_render_styles(self):
        # example for render styles in html.
        # should probably be overridden when subclassed
        return [
            ("emphasized_style", "<em>", "</em>"),
            ("strong_style", "<strong>", "</strong>"),
            ("small_style", "<small>", "</small>"),
            ("big_style", "<big>", "</big>"),
            ("sub_style", "<sub>", "</sub>"),
            ("sup_style", "<sup>", "</sup>"),
            ("teletype_style", "<tt>", "</tt>"),
            ("strike_style", "<strike>", "</strike>"),
            ("underline_style", "<u>", "</u>"),
            ("overline_style", "", ""),
        ]

    # noinspection PyMethodMayBeStatic
    def register_node_styles(self):
        return {
            advtree.Emphasized: "emphasized_style",
            advtree.Strong: "strong_style",
            advtree.Small: "small_style",
            advtree.Big: "big_style",
            advtree.Sub: "sub_style",
            advtree.Sup: "sup_style",
            advtree.Teletyped: "teletype_style",
            advtree.Code: "teletype_style",
            advtree.Var: "teletype_style",
            advtree.Strike: "strike_style",
            advtree.Underline: "underline_style",
            advtree.Overline: "overline_style",
        }

    def start_style(self):
        start = []
        for style, style_start, _, start_arg in self.render_styles:
            attr = getattr(self, style, 0)
            if not isinstance(attr, int):
                print(attr)
            # if getattr(self, style, 0) > 0:
            if getattr(self, style, 0) != 0:
                if start_arg:
                    start.append(style_start % getattr(self, start_arg))
                else:
                    start.append(style_start)
        if start:
            start.insert(0, self.grouping_chars[0])
        return "".join(start)

    def end_style(self):
        end = []
        # reverse style list
        for style, _, style_end, _ in self.render_styles[::-1]:
            if getattr(self, style, 0) != 0:
                end.append(style_end)
        if end:
            end.append(self.grouping_chars[1])
        return "".join(end)

    def set_relative_font_size(self, rel_font_size):
        # ignore anything too large. see search engine optimized article
        # http://fr.wikipedia.org/wiki/Licensed_to_Ill
        # (template "Infobox Musique (œuvre)")
        if rel_font_size > 10:
            return
        rel_font_size = min(rel_font_size, 5)
        self.fontsize_style += 1
        self.rel_font_size = rel_font_size

    def check_font_size(self, node_style):
        font_style = node_style.get("font-size")
        if not font_style:
            return

        size, unit = styleutils.parse_length(font_style)
        if size and unit in ["%", "pt", "px", "em"]:
            if unit == "%":
                self.set_relative_font_size(size / 100)
            elif unit == "pt":
                self.set_relative_font_size(size / 10)
            elif unit == "px":
                self.set_relative_font_size(size / 12)
            elif unit == "em":
                self.set_relative_font_size(size)
            return

        if font_style == "xx-small":
            self.set_relative_font_size(0.5)
        elif font_style == "x-small":
            self.set_relative_font_size(0.75)
        elif font_style == "small":
            self.set_relative_font_size(1.0)
        elif font_style == "medium":
            self.set_relative_font_size(1.25)
        elif font_style == "large":
            self.set_relative_font_size(1.5)
        elif font_style in ["x-large", "xx-large"]:
            self.set_relative_font_size(1.75)

    def _modify_or_reset_render_style(self, action, render_style):
        if action == "change":
            setattr(self, render_style,
                    getattr(self, render_style) + 1)
        elif action == "reset":
            setattr(self, render_style, 0)

    def change_css_style(self, node):
        css = self.css_style_map
        for node_style, style_value in node.style.items():
            if node_style in css:
                for render_style, action in css[node_style].get(style_value,
                                                                []):
                    self._modify_or_reset_render_style(action, render_style)
                if list(css[node_style].keys()) == ["*"]:
                    attr_name, method = css[node_style]["*"]
                    val = method(node)
                    if val:
                        setattr(self, attr_name, val)

        self.check_font_size(node.style)

    def change_node_style(self, node):
        style = self.node_styles.get(node.__class__)
        if style:
            setattr(self, style, getattr(self, style) + 1)

    def get_current_styles(self):
        styles = []
        for style, start, end, start_attr in self.render_styles:
            styles.append((style, getattr(self, style)))
        styles.append(("rel_font_size", self.rel_font_size))
        return styles

    def set_style(self, node):
        current_styles = self.get_current_styles()
        self.change_node_style(node)
        self.change_css_style(node)
        return current_styles

    def reset_style(self, styles):
        for attr, val in styles:
            setattr(self, attr, val)

    def clear_styles(self, styles):
        for attr, val in styles:
            if attr == "rel_font_size":
                setattr(self, attr, 1)
            else:
                setattr(self, attr, 0)

    def clean_text(self, txt, break_long=False, escape=True):
        if not txt:
            return ""

        if self.pre_mode:
            txt = self.escape_text(txt)
            txt = self.pre_mode_hook(txt)
            txt = self.font_switcher.fontify_text(txt)
        else:
            if escape:
                if self.minimize_space_mode > 0 or (
                    break_long
                    and max(len(w) for w in txt.split(" ")) > self.word_split_len
                ):
                    txt = self.escape_and_hyphenate_text(txt)
                else:
                    txt = self.escape_text(txt)
            txt = self.font_switcher.fontify_text(txt, break_long=break_long)

        if self.section_title_mode:
            txt = txt.lstrip()
            self.section_title_mode = False

        if self.table_nesting > 0 and not self.source_mode and not self.pre_mode:
            txt = self.table_mode_hook(txt)

        if self.output_encoding:
            txt = txt.encode(self.output_encoding)
        return txt

    def style_text(self, txt, break_long=False):
        if not txt.strip():
            if self.output_encoding:
                txt = txt.encode(self.output_encoding)
            return txt
        styled = [
            self.start_style(),
            self.clean_text(txt, break_long=break_long),
            self.end_style(),
        ]
        return "".join(styled)

    def switch_font(self, font):
        self.last_font = self.default_font
        self.default_font = font

    def restore_font(self):
        self.default_font = self.last_font

    # the methods below are the ones that should probably be overriden when
    # subclassing the formatter

    # noinspection PyMethodMayBeStatic
    def pre_mode_hook(self, txt):
        return txt

    # noinspection PyMethodMayBeStatic
    def table_mode_hook(self, txt):
        # this is a stub for the table formatter
        return txt

    def escape_text(self, txt):
        return txt

    def escape_and_hyphenate_text(self, txt):
        return txt
