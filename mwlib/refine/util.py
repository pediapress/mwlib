
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.txt for additional licensing information.

import re

paramrx = re.compile("(?P<name>\w+) *= *(?P<value>(?:(?:\".*?\")|(?:\'.*?\')|(?:(?:\w|[%:])+)))")
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

    def __init__(self, magicwords):        
        self.alias_map = {}
        self.initAliasMap(self.default_magicwords)
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
