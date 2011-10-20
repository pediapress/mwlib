
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

import re
import htmlentitydefs

paramrx = re.compile(r"(?P<name>\w+)\s*=\s*(?P<value>(?:(?:\".*?\")|(?:\'.*?\')|(?:(?:\w|[%:#])+)))", re.DOTALL)
def parseParams(s):
    def style2dict(s):
        res = {}
        for x in s.split(';'):
            if ':' in x:
                var, value = x.split(':', 1)
                var = var.strip().lower()
                value = value.strip()
                res[var] = value

        return res
    
    def maybeInt(v):
        try:
            return int(v)
        except:
            return v
    
    r = {}
    for name, value in paramrx.findall(s):
        if value.startswith('"') or value.startswith("'"):
            value = value[1:-1]
            
        if name.lower() == 'style':
            value = style2dict(value)
            r['style'] = value
        else:
            r[name] = maybeInt(value)
    return r



class ImageMod(object):
    default_magicwords = [
        {u'aliases': [u'thumbnail', u'thumb'], u'case-sensitive': u'', u'name': u'img_thumbnail'},
        {u'aliases': [u'thumbnail=$1', u'thumb=$1'], u'case-sensitive': u'', u'name': u'img_manualthumb'},
        {u'aliases': [u'right'], u'case-sensitive': u'', u'name': u'img_right'},
        {u'aliases': [u'left'], u'case-sensitive': u'', u'name': u'img_left'},
        {u'aliases': [u'none'], u'case-sensitive': u'', u'name': u'img_none'},
        {u'aliases': [u'$1px'], u'case-sensitive': u'', u'name': u'img_width'},
        {u'aliases': [u'center', u'centre'], u'case-sensitive': u'', u'name': u'img_center'},
        {u'aliases': [u'framed', u'enframed', u'frame'], u'case-sensitive': u'', u'name': u'img_framed'},
        {u'aliases': [u'frameless'], u'case-sensitive': u'', u'name': u'img_frameless'},
        {u'aliases': [u'page=$1', u'page $1'], u'case-sensitive': u'', u'name': u'img_page'},
        {u'aliases': [u'upright', u'upright=$1', u'upright $1'], u'case-sensitive': u'', u'name': u'img_upright'},
        {u'aliases': [u'border'], u'case-sensitive': u'', u'name': u'img_border'},
        {u'aliases': [u'baseline'], u'case-sensitive': u'', u'name': u'img_baseline'},
        {u'aliases': [u'sub'], u'case-sensitive': u'', u'name': u'img_sub'},
        {u'aliases': [u'super', u'sup'], u'case-sensitive': u'', u'name': u'img_super'},
        {u'aliases': [u'top'], u'case-sensitive': u'', u'name': u'img_top'},
        {u'aliases': [u'text-top'], u'case-sensitive': u'', u'name': u'img_text_top'},
        {u'aliases': [u'middle'], u'case-sensitive': u'', u'name': u'img_middle'},
        {u'aliases': [u'bottom'], u'case-sensitive': u'', u'name': u'img_bottom'},
        {u'aliases': [u'text-bottom'], u'case-sensitive': u'', u'name': u'img_text_bottom'},
        {u'aliases': [u'link=$1'], u'case-sensitive': u'', u'name': u'img_link'},
        {u'aliases': [u'alt=$1'], u'case-sensitive': u'', u'name': u'img_alt'},
        ]

    def __init__(self, magicwords=None):        
        self.alias_map = {}
        self.initAliasMap(self.default_magicwords)
        if magicwords is not None:
            self.initAliasMap(magicwords)

    def initAliasMap(self, magicwords):
        for m in magicwords:            
            if not m['name'].startswith('img_'):
                continue
            name = m['name']
            aliases = m['aliases']
            aliases_regexp = '|'.join(['^(%s)$' % re.escape(a) for a in aliases])
            if name == 'img_upright':
                aliases_regexp = aliases_regexp.replace('\\$1', '\\s*([0-9.]+)\\s*')
            elif name == 'img_width':
                aliases_regexp = aliases_regexp.replace('\\$1', '\\s*([0-9x]+)\\s*')
            elif name in ['img_alt', 'img_link']:
                aliases_regexp = aliases_regexp.replace('\\$1', '(.*)')
            self.alias_map[name] = aliases_regexp

    def parse(self, mod):
        mod = mod.lower().strip()
        for mod_type, mod_reg in self.alias_map.items():
            rx = re.compile(mod_reg, re.IGNORECASE)
            mo = rx.match(mod)
            if mo:
                for match in  mo.groups()[::-1]:
                    if match:
                        return (mod_type, match)
        return (None, None)



def handle_imagemod(self, mod_type, match):
    if mod_type == 'img_alt':
        self.alt = match

    if mod_type == 'img_link':
        self.link = match

    if mod_type == 'img_thumbnail':
        self.thumb = True

    if mod_type == 'img_left':
        self.align = 'left'
    if mod_type == 'img_right':
        self.align = 'right'
    if mod_type == 'img_center':
        self.align = 'center'
    if mod_type == 'img_none':
        self.align = 'none'
    if mod_type == 'img_framed':
        self.frame = 'frame'
    if mod_type == 'img_frameless':
        self.frame = 'frameless'

    if mod_type == 'img_border':
        self.border = True

    if mod_type == 'img_upright':
        try:
            scale = float(match)
        except ValueError:
            scale = 0.75
        self.upright = scale

    if mod_type == 'img_width':                
        # x200px or 100x200px or 200px
        width, height = (match.split('x')+['0'])[:2]
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
    if e[1]=='#':
        try:
            if e[2]=='x' or e[2]=='X':
                return unichr(int(e[3:-1], 16))
            else:
                return unichr(int(e[2:-1]))
        except ValueError:
            return e        
    else:
        try:
            return unichr(htmlentitydefs.name2codepoint[e[1:-1]])
        except KeyError:
            return e

def replace_html_entities(txt):
    return re.sub("&.*?;", lambda mo: resolve_entity(mo.group(0)), txt)

def remove_nowiki_tags(txt, _rx=re.compile("<nowiki>(.*?)</nowiki>",  re.IGNORECASE | re.DOTALL)):
    return _rx.sub(lambda mo: mo.group(1), txt)
