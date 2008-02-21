#! /usr/bin/env python

# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.

import sys
import time
import _mwscan
import htmlentitydefs

class token(object):
    t_end = 0
    t_text = 1
    t_entity = 2
    t_special = 3
    t_magicword = 4
    t_comment = 5
    t_2box_open = 6
    t_2box_close = 7
    t_http_url = 8
    t_break = 9
    t_begin_table = 10
    t_end_table = 11
    t_html_tag = 12
    t_style = 13
    t_pre = 14
    t_section = 15
    t_section_end = 16
    t_item = 17
    t_colon = 18
    t_semicolon = 19
    t_hrule = 20
    
    token2name = {}

for d in dir(token):
    token2name = token.token2name
    if d.startswith("t_"):
        token2name[getattr(token, d)] = d
del d

        
        
    
def dump_tokens(text, tokens):
    for type, start, len in tokens:
        print type, repr(text[start:start+len])
           
def scan(text):
    stime=time.time()
    text += u"\0"*32    
    tokens = _mwscan.scan(text)
    print "scan took:", time.time()-stime
    return scan_result(text, tokens)

def resolve_entity(e):
    if e[1]=='#':
        if e[2]=='x' or e[2]=='X':
            return unichr(int(e[3:-1], 16))
        else:
            return unichr(int(e[2:-1]))

    else:
        return htmlentitydefs.name2codepoint.get(e, e)

class scan_result(object):
    def __init__(self, source, toks):
        self.source = source
        self.toks = toks
        
    def rawtext(self, (type, start, tlen)):
        return self.source[start:start+tlen]

    def text(self, t):
        r=self.rawtext(t)
        if t[0] == token.t_entity:
            return resolve_entity(r)
        else:
            return r

    def dump(self, out=None):
        if out is None:
            out = sys.stdout
        for x in self:
            out.write("%s\n" % self.repr(x))

            
        
    def repr(self, t):
        return "(%s, %r)" % (token.token2name.get(t[0]), self.rawtext(t))


    def __len__(self):     
        return len(self.toks)

    def __iter__(self):
        return iter(self.toks)

    def __getitem__(self, idx):
        return self.toks[idx]


class _compat_scanner(object):
    class ignore: pass
    tok2compat = {
        token.t_text: "TEXT",
        token.t_special: "SPECIAL",
        token.t_2box_open: "[[",
        token.t_2box_close: "]]",
        token.t_http_url: "URL",
        token.t_break: "BREAK",
        token.t_style: "STYLE", 
        token.t_pre: "PRE",
        token.t_section: "SECTION",
        token.t_section_end: "ENDSECTION",
        token.t_magicword: ignore,
        token.t_comment: ignore,
        token.t_end: ignore,
        token.t_item: "ITEM",
        token.t_colon: "EOLSTYLE",
        token.t_semicolon: "EOLSTYLE",
        }
    
    def __call__(self, text):
        tokens = scan(text)

        res = []

        def g():
            return text[start:start+len]
        a = lambda x: res.append((x,g()))


        ignore = self.ignore
        tok2compat = self.tok2compat

        for type, start, len in tokens:
            n=tok2compat.get(type)
            if n is ignore:
                pass
            elif n is not None:
                a(n)
            elif type==token.t_entity:
                res.append(("TEXT", resolve_entity(g())))
            elif type==token.t_begin_table:
                pass # XXX
            elif type==token.t_end_table:
                pass # XXX
            elif type==token.t_html_tag:
                s = g()
                res.append((self.tagtoken(s), s))
            else:
                a(type)

        return res

    def tagtoken(self, text):
        selfClosing = False
        if text.startswith(u"</"):
            name = text[2:-1]
            klass = EndTagToken
            isEndToken = True
        elif text.endswith("/>"):
            name = text[1:-2]
            klass = TagToken
            selfClosing = True
            isEndToken = False # ???
        else:
            name = text[1:-1]
            klass = TagToken
            isEndToken = False

        name, values = (name.split(None, 1)+[u''])[:2]
        from mwlib.parser import paramrx
        values = dict(paramrx.findall(values))
        name = name.lower()

        if name=='br' or name=='references':
            isEndToken = False
            klass = TagToken

        r = klass(name, text)
        r.selfClosing = selfClosing
        r.values = values
        return r

        
        
compat_scan = _compat_scanner()

from plexscanner import _BaseTagToken, TagToken, EndTagToken

def tokenize(input, name="unknown"):
    assert input is not None, "must specify input argument in tokenize"
    return compat_scan(input)
