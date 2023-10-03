# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.


import re

import six.moves.html_entities
from six import unichr

param_rx = re.compile(
    r"(?P<name>\w+)\s*=\s*(?P<value>\"[^\"]*\"|\'[^\']*\'|[\w%:#]+)", re.DOTALL
)


def parse_params(input_string):
    def style2dict(s_val):
        res = {}
        for style_item in s_val.split(";"):
            if ":" in style_item:
                var, val = style_item.split(":", 1)
                var = var.strip().lower()
                val = val.strip()
                res[var] = val

        return res

    def maybe_int(value):
        try:
            return int(value)
        except ValueError:
            return value

    parsed_parameters = {}
    for name, value in param_rx.findall(input_string):
        if value.startswith('"') or value.startswith("'"):
            value = value[1:-1]

        if name.lower() == "style":
            value = style2dict(value)
            parsed_parameters["style"] = value
        else:
            parsed_parameters[name] = maybe_int(value)
    return parsed_parameters


class ImageMod:
    default_magicwords = [
        {
            "aliases": ["thumbnail", "thumb"],
            "case-sensitive": "",
            "name": "img_thumbnail",
        },
        {
            "aliases": ["thumbnail=$1", "thumb=$1"],
            "case-sensitive": "",
            "name": "img_manualthumb",
        },
        {"aliases": ["right"], "case-sensitive": "", "name": "img_right"},
        {"aliases": ["left"], "case-sensitive": "", "name": "img_left"},
        {"aliases": ["none"], "case-sensitive": "", "name": "img_none"},
        {"aliases": ["$1px"], "case-sensitive": "", "name": "img_width"},
        {"aliases": ["center", "centre"], "case-sensitive": "",
         "name": "img_center"},
        {
            "aliases": ["framed", "enframed", "frame"],
            "case-sensitive": "",
            "name": "img_framed",
        },
        {"aliases": ["frameless"], "case-sensitive": "",
         "name": "img_frameless"},
        {"aliases": ["page=$1", "page $1"], "case-sensitive": "",
         "name": "img_page"},
        {
            "aliases": ["upright", "upright=$1", "upright $1"],
            "case-sensitive": "",
            "name": "img_upright",
        },
        {"aliases": ["border"], "case-sensitive": "",
         "name": "img_border"},
        {"aliases": ["baseline"], "case-sensitive": "", "name": "img_baseline"},
        {"aliases": ["sub"], "case-sensitive": "", "name": "img_sub"},
        {"aliases": ["super", "sup"], "case-sensitive": "", "name": "img_super"},
        {"aliases": ["top"], "case-sensitive": "",
         "name": "img_top"},
        {"aliases": ["text-top"], "case-sensitive": "", "name": "img_text_top"},
        {"aliases": ["middle"], "case-sensitive": "", "name": "img_middle"},
        {"aliases": ["bottom"], "case-sensitive": "", "name": "img_bottom"},
        {"aliases": ["text-bottom"], "case-sensitive": "",
         "name": "img_text_bottom"},
        {"aliases": ["link=$1"], "case-sensitive": "", "name": "img_link"},
        {"aliases": ["alt=$1"], "case-sensitive": "", "name": "img_alt"},
    ]

    def __init__(self, magicwords=None):
        self.alias_map = {}
        self.init_alias_map(self.default_magicwords)
        if magicwords is not None:
            self.init_alias_map(magicwords)

    def init_alias_map(self, magicwords):
        for magic in magicwords:
            if not magic["name"].startswith("img_"):
                continue
            name = magic["name"]
            aliases = magic["aliases"]
            aliases_regexp = "|".join(["^(%s)$" % re.escape(a) for a in aliases])
            if name == "img_upright":
                aliases_regexp = aliases_regexp.replace("\\$1",
                                                        "\\s*([0-9.]+)\\s*")
            elif name == "img_width":
                aliases_regexp = aliases_regexp.replace("\\$1",
                                                        "\\s*([0-9x]+)\\s*")
            elif name in ["img_alt", "img_link"]:
                aliases_regexp = aliases_regexp.replace("\\$1", "(.*)")
            self.alias_map[name] = aliases_regexp

    def parse(self, mod):
        mod = mod.lower().strip()
        for mod_type, mod_reg in self.alias_map.items():
            compiled_regex = re.compile(mod_reg, re.IGNORECASE)
            regex_match = compiled_regex.match(mod)
            if regex_match:
                for match in regex_match.groups()[::-1]:
                    if match:
                        return mod_type, match
        return None, None


def handle_img_alt(self, match):
    self.alt = match


def handle_img_link(self, match):
    self.link = match


def handle_img_thumbnail(self):
    self.thumb = True


def handle_img_align(self, mod_type):
    if mod_type == "img_left":
        self.align = "left"
    if mod_type == "img_right":
        self.align = "right"
    if mod_type == "img_center":
        self.align = "center"
    if mod_type == "img_none":
        self.align = "none"


def handle_img_frame(self, mod_type):
    if mod_type == "img_framed":
        self.frame = "frame"
    if mod_type == "img_frameless":
        self.frame = "frameless"


def handle_img_border(self):
    self.border = True


def handle_img_upright(self, match):
    try:
        scale = float(match)
    except ValueError:
        scale = 0.75
    self.upright = scale


def handle_img_width(self, match):
    # x200px or 100x200px or 200px
    width, height = (match.split("x") + ["0"])[:2]
    try:
        width = int(width)
    except ValueError:
        width = 0

    try:
        height = int(height)
    except ValueError:
        height = 0

    self.width = width
    self.height = height


def handle_imagemod(self, mod_type, match):
    if mod_type == "img_alt":
        handle_img_alt(self, match)

    if mod_type == "img_link":
        handle_img_link(self, match)

    if mod_type == "img_thumbnail":
        handle_img_thumbnail(self)

    if mod_type in ["img_left", "img_right", "img_center", "img_none"]:
        handle_img_align(self, mod_type)

    if mod_type in ["img_framed", "img_frameless"]:
        handle_img_frame(self, mod_type)

    if mod_type == "img_border":
        handle_img_border(self)

    if mod_type == "img_upright":
        handle_img_upright(self, match)

    if mod_type == "img_width":
        handle_img_width(self, match)


def resolve_entity(entity):
    if entity[1] == "#":
        try:
            if entity[2] == "x" or entity[2] == "X":
                return unichr(int(entity[3:-1], 16))
            else:
                return unichr(int(entity[2:-1]))
        except ValueError:
            return entity
    else:
        try:
            return unichr(six.moves.html_entities.name2codepoint[entity[1:-1]])
        except KeyError:
            return entity


def replace_html_entities(txt):
    return re.sub(r"&[^;]*;", lambda mo: resolve_entity(mo.group(0)), txt)


def remove_nowiki_tags(
    txt, _rx=re.compile("<nowiki>(.*?)</nowiki>", re.IGNORECASE | re.DOTALL)
):
    return _rx.sub(lambda mo: mo.group(1), txt)
