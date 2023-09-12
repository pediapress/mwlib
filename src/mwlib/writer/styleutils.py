#!/usr/bin/env python

# Copyright (c) 2007-2023 PediaPress GmbH
# See README.rst for additional licensing information.

import re
from typing import Optional

from mwlib import advtree
from mwlib.htmlcolornames import colorname2rgb_map

mw_px2pt = 12 / 16
mw_em2pt = 9.6


def _color_from_str(color_str: str) -> Optional[tuple[float, float, float]]:
    def hex2rgb(r: str, g: str,
                b: str) -> Optional[tuple[float, float, float]]:
        try:

            def conv(c: str) -> float:
                return max(0.0, min(1.0, int(c, 16) / 255))

            return conv(r), conv(g), conv(b)
        except ValueError:
            return None

    def hexshort2rgb(r: str, g: str,
                     b: str) -> Optional[tuple[float, float, float]]:
        try:

            def conv(c: str) -> float:
                return float(max(0.0, min(1.0, int(2 * c, 16) / 255)))

            return conv(r), conv(g), conv(b)
        except ValueError:
            return None

    def rgb2rgb(r: str, g: str,
                b: str) -> Optional[tuple[float, float, float]]:
        try:

            def conv(c: str) -> float:
                return max(0.0, min(1.0, int(c) / 255))

            return conv(r), conv(g), conv(b)
        except ValueError:
            return None

    def colorname2rgb(color_str_param: str) -> Optional[tuple[float, ...]]:
        rgb = colorname2rgb_map.get(color_str_param.lower(), None)
        if rgb:
            return tuple(max(0.0, min(1, channel / 255)) for channel in rgb)
        else:
            return None

    def get_rgbval(color_str: str):
        search_str = "rgb\\( *(\\d+) *, *(\\d{1,3}) *, *(\\d{1,3}) *\\)"
        return re.search(search_str, color_str)

    try:
        color_str = str(color_str)
    except ValueError:
        return None
    rgbval = get_rgbval(color_str)
    hexval = re.search("#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})", color_str)
    hexvalshort = re.search("#([0-9a-f])([0-9a-f])([0-9a-f])", color_str)
    if rgbval:
        return rgb2rgb(rgbval.group(1), rgbval.group(2), rgbval.group(3))
    elif hexval:
        return hex2rgb(hexval.group(1), hexval.group(2), hexval.group(3))
    elif hexvalshort:
        return hexshort2rgb(
            hexvalshort.group(1), hexvalshort.group(2), hexvalshort.group(3)
        )
    else:
        return colorname2rgb(color_str)


def _rgb_to_greyscale(
    rgb_triple: tuple[float, float, float], darkness_limit: float = 1.0
) -> tuple[float, float, float]:
    grey = min(
        1.0,
        max(
            darkness_limit,
            0.3 * rgb_triple[0] + 0.59 * rgb_triple[1] + 0.11 * rgb_triple[2],
        ),
    )
    return grey, grey, grey


def rgb_bg_color_from_node(
    node: advtree.Node,
    grey_scale: bool = False,
    darkness_limit: float = 0,
    follow: bool = True,
) -> Optional[tuple[float, float, float]]:
    color_str = (
        node.attributes.get("bgcolor", None)
        or node.style.get("background")
        or node.style.get("background-color")
    )

    color = None
    if color_str:
        color = _color_from_str(color_str.lower())
        if grey_scale and color:
            return _rgb_to_greyscale(color, darkness_limit)
    elif node.parent and follow:
        return rgb_bg_color_from_node(
            node.parent, grey_scale=grey_scale, darkness_limit=darkness_limit
        )
    return color


def _get_color(node):
    color_str = node.style.get("color", None)
    if color_str:
        return color_str
    return node.attributes.get("color", None)


def rgb_color_from_node(
    node: advtree.Node,
    grey_scale: bool = False,
    darkness_limit: float = 0,
) -> Optional[tuple[float, float, float]]:
    color_str = _get_color(node)
    color = None
    if color_str:
        color = _color_from_str(color_str.lower())
        if grey_scale and color:
            return _rgb_to_greyscale(color, darkness_limit)
    elif node.parent:
        return rgb_color_from_node(
            node.parent, grey_scale=grey_scale, darkness_limit=darkness_limit
        )
    return color


def get_base_alignment(node: advtree.Node) -> str:
    if isinstance(node, advtree.Cell) and getattr(node, "is_header", False):
        return "center"
    return "none"


def _get_text_alignment(node: advtree.Node) -> str:
    align = node.style.get("text-align", "none").lower()
    allowed_instances = (advtree.Div, advtree.Cell, advtree.Row)
    if align == "none" and isinstance(node, allowed_instances):
        align = node.attributes.get("align", "none").lower()
    if align not in ["left", "center", "right", "justify", "none"]:
        return "left"
    if isinstance(node, advtree.Center):
        align = "center"
    if align == "none" and node.parent:
        return _get_text_alignment(node.parent)
    return align


def get_text_alignment(node: advtree.Node) -> str:
    nodes = node.get_parents()
    nodes.append(node)
    align = get_base_alignment(node)
    for n in nodes:
        parent_align = _get_text_alignment(n)
        if parent_align != "none":
            align = parent_align
    return align


def _get_alignment_from_node(node: advtree.Node) -> str:
    align = node.style.get("vertical-align", None)
    if align:
        return align
    return node.vlist.get("valign", None)


def get_vertical_alignment(node: advtree.Node) -> str:
    align = None
    for n in node.parents + [node]:
        _align = _get_alignment_from_node(n)
        if _align in ["top", "middle", "bottom"]:
            align = _align
    return align or "top"


def get_bg_color(attributes, style) -> Optional[str]:
    return attributes.get("background-color") or style.get("background-color")


def table_border(node: advtree.Node) -> bool:
    border_boxes = [
        "prettytable",
        "metadata",
        "wikitable",
        "infobox",
        "ujinfobox",
        "infobox_v2",
        "infoboks",
        "toccolours",
        "navbox",
        "float-right",
        "taxobox",
        "info",
        "collapsibleTable0",
        "palaeobox",
    ]
    no_border_boxes = [
        "cquote",
    ]
    attributes = node.attributes
    style = attributes.get("style", {})

    classes = {c.strip() for c in attributes.get("class", "").split()}
    if set(border_boxes).intersection(classes):
        return True
    if set(no_border_boxes).intersection(classes):
        return False
    if style.get("border-style", None) == "none":
        return False
    if (
        attributes.get("border", "0") != "0"
        or style.get("border", "0") != "0"
        or style.get("border-style", "none") != "none"
        or style.get("border-width", "0") != "0"
    ):
        return True

    bg_color = get_bg_color(attributes, style)
    if bg_color and bg_color != "transparent":
        return True

    bs = attributes.get("border-spacing", None)
    if bs:
        bs_val = re.match(r"(?P<bs>\d)", bs)
        if bs_val and int(bs_val.group("bs")) > 0:
            return True

    return False


def parse_length(txt: str) -> tuple[Optional[float], Optional[str]]:
    length_res = re.search(r"(?P<val>.*?)(?P<unit>(pt|px|em|%))", txt)
    length = unit = None
    if length_res:
        unit = length_res.group("unit")
        try:
            length = float(length_res.group("val"))
        except ValueError:
            length = None
    return length, unit


def scale_length(length_str, reference=None):
    length, unit = parse_length(length_str)
    if not length:
        return 0
    if unit == "pt":
        return length
    elif unit == "px":
        return length * mw_px2pt
    elif unit == "em":
        return length * mw_em2pt
    elif unit == "%" and reference:
        return length / 100 * reference
    return 0
