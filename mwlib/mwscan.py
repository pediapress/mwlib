#! /usr/bin/env python

import time
import _mwscan
import htmlentitydefs

class token:
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

def dump_tokens(text, tokens):
    for type, start, len in tokens:
        print type, repr(text[start:start+len])
           
def scan(text):
    stime=time.time()
    text += u"\0"*32    
    tokens = _mwscan.scan(text)
    print "scan took:", time.time()-stime
    return tokens

def resolve_entity(e):
    if e[1]=='#':
        if e[2]=='x' or e[2]=='X':
            return unichr(int(e[3:-1], 16))
        else:
            return unichr(int(e[2:-1]))

    else:
        return htmlentitydefs.name2codepoint.get(e, e)
    

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
                pass # XXX
            else:
                a(type)

        return res

compat_scan = _compat_scanner()
