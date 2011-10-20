
# Copyright (c) 2009 PediaPress GmbH
# See README.rst for additional licensing information.

"""parse tags in parallel"""

import sys
from mwlib.utoken import token as T

class taginfo(object):
    def __init__(self, tagname=None, prio=None, blocknode=False,  nested=True):
        assert None not in (tagname, prio, nested, blocknode)
        self.tagname = tagname
        self.prio = prio
        self.nested = nested
        self.blocknode = blocknode
                 
class tagparser(object):
    def __init__(self, tags=[]):
        self.name2tag = name2tag = {}
        for t in tags:
            name2tag[t.tagname] = t

        self.guard = (None, taginfo(tagname="", prio=sys.maxint, nested=True, blocknode=False))

    def add(self, tagname=None,  prio=None, blocknode=False, nested=True):
        t = taginfo(tagname=tagname, prio=prio, blocknode=blocknode, nested=nested)
        self.name2tag[t.tagname] = t
        
    def find_in_stack(self, tag):
        pos = len(self.stack)-1
        while pos>0:
            _, t = self.stack[pos]
            if t.tagname==tag.tagname:
                return pos
            
            if tag.prio > t.prio:
                pos -= 1
            else:
                break
            
        return 0

    def close_stack(self, spos, tokens, pos):
        close = self.stack[spos:]
        del self.stack[spos:]
        close.reverse()
        
        for i, t in close:
            vlist=tokens[i].vlist
            display = vlist.get("style", {}).get("display", "").lower()
            if display=="inline":
                blocknode = False
            elif display=="block":
                blocknode = True
            else:
                blocknode=t.blocknode
            
            sub = tokens[i+1:pos]
            tokens[i:pos] = [T(type=T.t_complex_tag,  children=sub,  tagname=t.tagname, blocknode=blocknode,  vlist=tokens[i].vlist)]
            pos = i+1
            
        return pos
    
    
    def __call__(self, tokens,  xopts):
        pos=0
        self.stack = stack = [self.guard]
        get = self.name2tag.get
        
        while pos<len(tokens):
            t = tokens[pos]
            # print t
            tag = get(t.rawtagname)
            if tag is None:
                pos += 1
                continue
            if t.type==T.t_html_tag:
                if t.tag_selfClosing:
                    tokens[pos].type = T.t_complex_tag
                    tokens[pos].tagname = tokens[pos].rawtagname
                    tokens[pos].rawtagname = None 
                    pos += 1
                else:
                    if stack[-1][1].prio==tag.prio and not tag.nested:
                        pos = self.close_stack(len(stack)-1, tokens, pos)
                        assert tokens[pos] is t
                        
                    stack.append((pos,  tag))
                    pos+=1
            else:
                assert t.type==T.t_html_tag_end
                # find a matching tag in the stack
                spos = self.find_in_stack(tag)
                if spos:
                    pos = self.close_stack(spos, tokens, pos)
                    assert tokens[pos] is t
                    del tokens[pos]
                else:
                    pos += 1
                    
        self.close_stack(1, tokens, pos)
