# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.



import re

import six.moves.html_entities
from six import unichr

param_rx = re.compile(r"(?P<name>\w+)\s*=\s*(?P<value>\"[^\"]*\"|\'[^\']*\'|[\w%:#]+)", re.DOTALL)


def parse_params(s):
    def style2dict(s_val):
        res = {}
        for x in s_val.split(";"):
            if ":" in x:
                var, val = x.split(":", 1)
                var = var.strip().lower()
                val = val.strip()
                res[var] = val

        return res

    def maybe_int(v):
        try:
            return int(v)
        except ValueError:
            return v

    r = {}
    for name, value in param_rx.findall(s):
        if value.startswith('"') or value.startswith("'"):
            value = value[1:-1]

        if name.lower() == "style":
            value = style2dict(value)
            r["style"] = value
        else:
            r[name] = maybe_int(value)
    return r


class ImageMod:
    default_magicwords = [
        {"aliases": ["thumbnail", "thumb"], "case-sensitive": "", "name": "img_thumbnail"},
        {
            "aliases": ["thumbnail=$1", "thumb=$1"],
            "case-sensitive": "",
            "name": "img_manualthumb",
        },
        {"aliases": ["right"], "case-sensitive": "", "name": "img_right"},
        {"aliases": ["left"], "case-sensitive": "", "name": "img_left"},
        {"aliases": ["none"], "case-sensitive": "", "name": "img_none"},
        {"aliases": ["$1px"], "case-sensitive": "", "name": "img_width"},
        {"aliases": ["center", "centre"], "case-sensitive": "", "name": "img_center"},
        {
            "aliases": ["framed", "enframed", "frame"],
            "case-sensitive": "",
            "name": "img_framed",
        },
        {"aliases": ["frameless"], "case-sensitive": "", "name": "img_frameless"},
        {"aliases": ["page=$1", "page $1"], "case-sensitive": "", "name": "img_page"},
        {
            "aliases": ["upright", "upright=$1", "upright $1"],
            "case-sensitive": "",
            "name": "img_upright",
        },
        {"aliases": ["border"], "case-sensitive": "", "name": "img_border"},
        {"aliases": ["baseline"], "case-sensitive": "", "name": "img_baseline"},
        {"aliases": ["sub"], "case-sensitive": "", "name": "img_sub"},
        {"aliases": ["super", "sup"], "case-sensitive": "", "name": "img_super"},
        {"aliases": ["top"], "case-sensitive": "", "name": "img_top"},
        {"aliases": ["text-top"], "case-sensitive": "", "name": "img_text_top"},
        {"aliases": ["middle"], "case-sensitive": "", "name": "img_middle"},
        {"aliases": ["bottom"], "case-sensitive": "", "name": "img_bottom"},
        {"aliases": ["text-bottom"], "case-sensitive": "", "name": "img_text_bottom"},
        {"aliases": ["link=$1"], "case-sensitive": "", "name": "img_link"},
        {"aliases": ["alt=$1"], "case-sensitive": "", "name": "img_alt"},
    ]

    def __init__(self, magicwords=None):
        self.alias_map = {}
        self.init_alias_map(self.default_magicwords)
        if magicwords is not None:
            self.init_alias_map(magicwords)

    def init_alias_map(self, magicwords):
        for m in magicwords:
            if not m["name"].startswith("img_"):
                continue
            name = m["name"]
            aliases = m["aliases"]
            aliases_regexp = "|".join(["^(%s)$" % re.escape(a) for a in aliases])
            if name == "img_upright":
                aliases_regexp = aliases_regexp.replace("\\$1", "\\s*([0-9.]+)\\s*")
            elif name == "img_width":
                aliases_regexp = aliases_regexp.replace("\\$1", "\\s*([0-9x]+)\\s*")
            elif name in ["img_alt", "img_link"]:
                aliases_regexp = aliases_regexp.replace("\\$1", "(.*)")
            self.alias_map[name] = aliases_regexp

    def parse(self, mod):
        mod = mod.lower().strip()
        for mod_type, mod_reg in self.alias_map.items():
            rx = re.compile(mod_reg, re.IGNORECASE)
            mo = rx.match(mod)
            if mo:
                for match in mo.groups()[::-1]:
                    if match:
                        return mod_type, match
        return None, None


def handle_imagemod(self, mod_type, match):
    if mod_type == "img_alt":
        self.alt = match

    if mod_type == "img_link":
        self.link = match

    if mod_type == "img_thumbnail":
        self.thumb = True

    if mod_type == "img_left":
        self.align = "left"
    if mod_type == "img_right":
        self.align = "right"
    if mod_type == "img_center":
        self.align = "center"
    if mod_type == "img_none":
        self.align = "none"
    if mod_type == "img_framed":
        self.frame = "frame"
    if mod_type == "img_frameless":
        self.frame = "frameless"

    if mod_type == "img_border":
        self.border = True

    if mod_type == "img_upright":
        try:
            scale = float(match)
        except ValueError:
            scale = 0.75
        self.upright = scale

    if mod_type == "img_width":
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


def resolve_entity(e):
    if e[1] == "#":
        try:
            if e[2] == "x" or e[2] == "X":
                return unichr(int(e[3:-1], 16))
            else:
                return unichr(int(e[2:-1]))
        except ValueError:
            return e
    else:
        try:
            return unichr(six.moves.html_entities.name2codepoint[e[1:-1]])
        except KeyError:
            return e


def replace_html_entities(txt):
    return re.sub(r"&[^;]*;", lambda mo: resolve_entity(mo.group(0)), txt)


def remove_nowiki_tags(txt, _rx=re.compile("<nowiki>(.*?)</nowiki>", re.IGNORECASE | re.DOTALL)):
    return _rx.sub(lambda mo: mo.group(1), txt)
