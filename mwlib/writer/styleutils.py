#! /usr/bin/env python
#! -*- coding:utf-8 -*-

# Copyright (c) 2007, PediaPress GmbH
# See README.txt for additional licensing information.

from __future__ import division
import re

from mwlib import advtree
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

def rgbBgColorFromNode(node, greyScale=False, darknessLimit=0):
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

def rgbColorFromNode(node, greyScale=False, darknessLimit=0):
    """Extract text color from node attributes/style. Result is a rgb triple w/ individual values between [0...1]"""

    colorStr = node.style.get('color', None) or \
               node.attributes.get('color', None)
    color = None
    if colorStr:
        color = _colorFromStr(colorStr.lower())
        if greyScale and color:
            return _rgb2GreyScale(color, darknessLimit)
    return color


def getTextAlign(node):
    """ return the text alignment of a node. possible return values are left|right|center|none"""
    if node.__class__ == advtree.Cell and getattr(node, 'is_header', False):
        return 'center'
    align = node.style.get('text-align', 'none').lower()
    if align == 'none' and node.__class__ in  [advtree.Div, advtree.Cell, advtree.Row]:
        align = node.attributes.get('align', 'none').lower()
    if align not in ['left', 'center', 'right', 'justify', 'none']:
        return 'left'
    if node.__class__ == advtree.Center:
        align = 'center'
    if align == "none" and node.parent:
        return getTextAlign(node.parent)
    return align

def tableBorder(node):
    borderBoxes = ['prettytable',
                   'metadata',
                   'wikitable',
                   'infobox',
                   'toccolours',
                   'navbox',
                   'float-right',
                   'taxobox',
                   'info',
                   'collapsibleTable0',
                   'palaeobox',
                   ]

    attributes = node.attributes
    style = attributes.get('style', {})

    classes = set([ c.strip() for c in attributes.get('class','').split()])
    if set(borderBoxes).intersection(classes):
        return True

    if style.get('border-style', None) == 'none':
        return False
    if attributes.get('border', "0") != "0" or \
           style.get('border', "0") != "0" or \
           style.get('border-style', "none") != 'none' or \
           style.get('border-width', "0") != "0":
        return True
    
    bgColor = attributes.get('background-color') or style.get('background-color')
    if bgColor and bgColor!= 'transparent':
        return True # FIXME this is probably not very accurate

    bs = attributes.get('border-spacing',None)
    if bs:
        bs_val = re.match('(?P<bs>\d)',bs)
        if bs_val and int(bs_val.groups('bs')[0]) > 0:
            return True

    return False

def parseLength(txt):
    length_res = re.search(r'(?P<val>.*?)(?P<unit>(pt|px|em|%))', txt)
    length = unit = None
    if length_res:
        unit = length_res.group('unit')
        try:
            length = float(length_res.group('val'))
        except ValueError:
            length = None
    return (length, unit)
    
            
def scaleLength(length_str):
    length, unit = parseLength(length_str)
    if unit == 'pt':
        return length
    elif unit == 'px':
        return length * 10/12
    elif unit == 'em':
        return length * 10
    return 0
