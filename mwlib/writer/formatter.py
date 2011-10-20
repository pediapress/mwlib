#! /usr/bin/env python
#! -*- coding:utf-8 -*-

# Copyright (c) 2007, PediaPress GmbH
# See README.rst for additional licensing information.

from __future__ import division

from mwlib.writer import styleutils
from mwlib import advtree

class Formatter(object):
    """store the current formatting state"""


    css_style_map = {'font-style': {'italic': [('emphasized_style', 'change')],
                                    'oblique': [('emphasized_style', 'change')],
                                    'normal': [('emphasized_style', 'reset')]
                                    },
                     'font-family': {'Courier':[('teletype_style', 'change')],
                                     },
                     'font-weight': {'bold': [('strong_style', 'change')],
                                     'bolder': [('strong_style', 'change')], # bolder and bold are treated the same
                                     'normal': [('strong_style', 'reset')],
                                     'lighter': [('strong_style', 'reset')], # treat lighter as normal
                                     },
                     'text-decoration': {'overline': [('overline_style', 'change'),
                                                      ('underline_style', 'reset'),
                                                      ('strike_style', 'reset'),
                                                      ],
                                         'underline': [('underline_style', 'change'),
                                                       ('overline_style', 'reset'),
                                                       ('strike_style', 'reset'),
                                                       ],
                                         'line-through': [('strike_style', 'change'),
                                                          ('underline_style', 'reset'),
                                                          ('overline_style', 'reset'),
                                                          ],
                                         },
                     'color': {'*':('color_style', styleutils.rgbColorFromNode)
                               },
                     }


    def __init__(self, font_switcher=None, output_encoding=None, word_split_len=20):

        self.font_switcher = font_switcher

        self.default_font = 'DejaVuSerif'
        self.default_mono_font = 'DejaVuSansMono'

        self.output_encoding = output_encoding

        self.render_styles = self.registerRenderStyles()
        self.node_styles = self.registerNodeStyles()
        
        for style, start_style, end_style, start_attr in self.render_styles:
            setattr(self, style, 0)
       
        self.source_mode = 0 
        self.pre_mode = 0
        self.index_mode = 0
        self.gallery_mode = 0
        self.footnote_mode = 0
        self.minimize_space_mode = 0 # used for tables if we try to safe space
        
        self.sectiontitle_mode = False
        self.attribution_mode = True
        self.last_font = None
        self.table_nesting = 0
        self.rel_font_size = 1

        self.grouping_chars = ('', '')
        self.word_split_len = word_split_len

    def registerRenderStyles(self):
        # example for render styles in html. should probably be overridden when subclassed
        return [
            ('emphasized_style', '<em>', '</em>'),
            ('strong_style', '<strong>', '</strong>'),
            ('small_style', '<small>', '</small>'),
            ('big_style', '<big>', '</big>'),
            ('sub_style', '<sub>', '</sub>'),
            ('sup_style', '<sup>','</sup>'),
            ('teletype_style', '<tt>', '</tt>'),
            ('strike_style', '<strike>', '</strike>'),
            ('underline_style', '<u>', '</u>'),
            ('overline_style', '', '')
            ]

    def registerNodeStyles(self):
        return {
            advtree.Emphasized:'emphasized_style',
            advtree.Strong: 'strong_style',
            advtree.Small: 'small_style',
            advtree.Big: 'big_style',
            advtree.Sub: 'sub_style',
            advtree.Sup: 'sup_style',
            advtree.Teletyped: 'teletype_style',
            advtree.Code: 'teletype_style',
            advtree.Var: 'teletype_style',
            advtree.Strike: 'strike_style',
            advtree.Underline: 'underline_style',
            advtree.Overline: 'overline_style',
            }

    def startStyle(self):
        start = []
        for style, style_start, style_end, start_arg in self.render_styles:
            if getattr(self, style, 0) > 0:
                if start_arg:
                    start.append(style_start % getattr(self, start_arg))
                else:
                    start.append(style_start)
        if start:
            start.insert(0, self.grouping_chars[0])
        return ''.join(start)

    def endStyle(self):
        end = []
        for style, style_start, style_end, start_arg in self.render_styles[::-1]: # reverse style list
            if getattr(self, style, 0) > 0:
                end.append(style_end)
        if end:
            end.append(self.grouping_chars[1])
        return ''.join(end)


    def setRelativeFontSize(self, rel_font_size):
        # ignore anything too large. see search engine optimized article
        # http://fr.wikipedia.org/wiki/Licensed_to_Ill (template "Infobox Musique (œuvre)")
        if rel_font_size > 10:
            return
        rel_font_size = min(rel_font_size, 5)
        self.fontsize_style += 1
        self.rel_font_size = rel_font_size
    
    def checkFontSize(self, node_style):
        font_style = node_style.get('font-size')
        if not font_style:
            return
                
        size, unit = styleutils.parseLength(font_style)
        if size and unit in ['%', 'pt', 'px', 'em']:
            if unit == '%':
                self.setRelativeFontSize(size/100)
            elif unit ==  'pt':
                self.setRelativeFontSize(size/10)
            elif unit ==  'px':
                self.setRelativeFontSize(size/12)
            elif unit ==  'em':
                self.setRelativeFontSize(size)
            return

        if font_style == 'xx-small':
            self.setRelativeFontSize(0.5)
        elif font_style == 'x-small':
            self.setRelativeFontSize(0.75)
        elif font_style == 'small':
            self.setRelativeFontSize(1.0)
        elif font_style == 'medium':
            self.setRelativeFontSize(1.25)
        elif font_style == 'large':
            self.setRelativeFontSize(1.5)
        elif font_style in ['x-large', 'xx-large']:
            self.setRelativeFontSize(1.75)
                           
    
    def changeCssStyle(self, node, mode=None):        
        css = self.css_style_map
        for node_style, style_value in node.style.items():
            if node_style in css:
                for render_style, action in css[node_style].get(style_value, []):
                    if action == 'change':
                        setattr(self, render_style, getattr(self, render_style) + 1)
                    elif action == 'reset':
                        setattr(self, render_style, 0)
                if css[node_style].keys() == ['*']:
                    attr_name, method = css[node_style]['*']
                    val = method(node)
                    if val:
                        setattr(self, attr_name, val)

        self.checkFontSize(node.style)

    def changeNodeStyle(self, node):
        style = self.node_styles.get(node.__class__)
        if style:
            setattr(self, style, getattr(self, style) + 1)

    def getCurrentStyles(self):
        styles = []
        for style, start, end, start_attr in self.render_styles:
            styles.append((style, getattr(self, style)))
        styles.append(('rel_font_size', self.rel_font_size))
        return styles
    
    def setStyle(self, node):
        current_styles = self.getCurrentStyles()
        self.changeNodeStyle(node)
        self.changeCssStyle(node, mode='set')
        return current_styles
            
    def resetStyle(self, styles):
        for attr, val in styles:
            setattr(self, attr, val)

    def clearStyles(self, styles):
        for attr, val in styles:
            if attr == 'rel_font_size':
                setattr(self, attr, 1)
            else:
                setattr(self, attr, 0)

    def cleanText(self, txt, break_long=False, escape=True):
        if not txt:
            return ''

        if self.pre_mode:
            txt = self.escapeText(txt)
            txt = self.pre_mode_hook(txt)
            txt = self.font_switcher.fontifyText(txt)
        elif self.source_mode:
            pass
        else:
            if escape:
                if self.minimize_space_mode > 0 or (break_long and max(len(w) for w in txt.split(' ')) > self.word_split_len):
                    txt = self.escapeAndHyphenateText(txt)
                else:
                    txt = self.escapeText(txt)
            txt = self.font_switcher.fontifyText(txt, break_long=break_long)

        if self.sectiontitle_mode:
            txt = txt.lstrip()
            self.sectiontitle_mode = False
            
        if self.table_nesting > 0 and not self.source_mode and not self.pre_mode:
            txt = self.table_mode_hook(txt)        

        if self.output_encoding:
            txt = txt.encode(self.output_encoding)
        return txt

    def styleText(self, txt, break_long=False):
        if not txt.strip():
            if self.output_encoding:
                txt = txt.encode(self.output_encoding)
            return txt
        styled = []
        styled.append(self.startStyle())
        styled.append(self.cleanText(txt, break_long=break_long))
        styled.append(self.endStyle())
        return ''.join(styled)


    def switchFont(self, font):
        self.last_font = self.default_font
        self.default_font = font

    def restoreFont(self):
        self.default_font = self.last_font


    ### the methods below are the ones that should probably be overriden when subclassing the formatter

    def pre_mode_hook(self, txt):
        return txt

    def table_mode_hook(self, txt):
        return txt

    def escapeText(self, txt): 
        return txt

    def escapeAndHyphenateText(self, txt):
        return txt
