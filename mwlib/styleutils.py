#! /usr/bin/env python
#! -*- coding:utf-8 -*-

# Copyright (c) 2007, PediaPress GmbH
# See README.txt for additional licensing information.

from __future__ import division
import  re

from mwlib.advtree import Center
from mwlib.htmlcolornames import colorname2rgb_map

def _colorFromStr(colorStr):

    def hex2rgb(r, g, b):
        try:
            return (int(r, 16) / 255, int(g, 16) / 255, int(b, 16) / 255)
        except ValueError:
            return None
    def hexshort2rgb(r, g, b):
        try:
            return (int(2*r, 16) / 255, int(2*g, 16) / 255, int(2*b, 16) / 255)
        except:
            return None           
    def rgb2rgb(r, g, b):
        try:
            return (int(r) / 255, int(g) / 255, int(b) / 255)
        except ValueError:
            return None
    def colorname2rgb(colorStr):
        rgb = colorname2rgb_map.get(colorStr.lower(), None)
        if rgb:
            return tuple(channel/255 for channel in rgb)
        else:
            return None
                   
    try:
        colorStr = str(colorStr)
    except:
        return None
    rgbval = re.search('rgb\( *(\d{1,}) *, *(\d{1,3}) *, *(\d{1,3}) *\)', colorStr)          
    hexval = re.search('#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})', colorStr)
    hexvalshort = re.search('#([0-9a-f])([0-9a-f])([0-9a-f])', colorStr)
    if rgbval:
        return rgb2rgb(rgbval.group(1), rgbval.group(2), rgbval.group(3))
    elif hexval:
        return hex2rgb(hexval.group(1), hexval.group(2), hexval.group(3))
    elif hexvalshort:
        return hexshort2rgb(hexvalshort.group(1), hexvalshort.group(2), hexvalshort.group(3))
    else:
        return colorname2rgb(colorStr)
    return None


def _rgb2GreyScale(rgb_triple, darknessLimit=1):
    grey = min(1, max(darknessLimit, 0.3*rgb_triple[0] + 0.59*rgb_triple[1] + 0.11*rgb_triple[2] ))
    return (grey, grey, grey)

def rgbBgColorFromNode(node, greyScale=False, darknessLimit=1):
    """Extract background color from node attributes/style. Result is a rgb triple w/ individual values between [0...1]

    The darknessLimit parameter is only used when greyScale is requested. This is for b/w output formats that do not
    switch text-color.
    """

    colorStr = node.attributes.get('bgcolor', None) or \
               node.style.get('background') or \
               node.style.get('background-color')
            
    color = None
    if colorStr:
        color = _colorFromStr(colorStr.lower())
        if greyScale and color:
            return _rgb2GreyScale(color, darknessLimit)
    return color

def rgbColorFromNode(node, greyScale=False, darknessLimit=1):
    """Extract text color from node attributes/style. Result is a rgb triple w/ individual values between [0...1]"""

    colorStr = node.style.get('color', None) or \
               node.attributes.get('color', None)
    color = None
    if colorStr:
        color = _colorFromStr(colorStr.lower())
        if greyScale and color:
            return _rgb2GreyScale(color, darknessLimit)
    return color

def alignmentFromNode(node):
    align = node.style.get('text-align', '').lower()
    if align in ['right', 'left', 'center', 'justify']:
        return align
    else: # special handling for nodes inside a center tag
        if node.getParentNodesByClass(Center):
            return 'center'
    return None

