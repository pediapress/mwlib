# Copyright (c) 2009 PediaPress GmbH
# See README.rst for additional licensing information.

"""parse tags in parallel"""

import sys

from mwlib.token.utoken import Token


class TagInfo:
    def __init__(self, tagname=None, prio=None, blocknode=False, nested=True):
        if any(x is None for x in (tagname, prio, nested, blocknode)):
            raise ValueError("None not allowed")
        self.tagname = tagname
        self.prio = prio
        self.nested = nested
        self.blocknode = blocknode


class TagParser:
    def __init__(self, tags=None):
        if tags is None:
            tags = []
        self.name2tag = name2tag = {}
        for tag in tags:
            name2tag[tag.tagname] = tag

        self.guard = (None, TagInfo(tagname="", prio=sys.maxsize,
                                    nested=True, blocknode=False))
        self.stack = []

    def add(self, tagname=None, prio=None, blocknode=False, nested=True):
        tag = TagInfo(tagname=tagname, prio=prio,
                      blocknode=blocknode, nested=nested)
        self.name2tag[tag.tagname] = tag

    def find_in_stack(self, tag):
        pos = len(self.stack) - 1
        while pos > 0:
            _, stacked_tag = self.stack[pos]
            if stacked_tag.tagname == tag.tagname:
                return pos

            if tag.prio > stacked_tag.prio:
                pos -= 1
            else:
                break

        return 0

    def close_stack(self, spos, tokens, pos):
        close = self.stack[spos:]
        del self.stack[spos:]
        close.reverse()

        i: int
        for i, tag in close:
            vlist = tokens[i].vlist
            display = vlist.get("style", {}).get("display", "").lower()
            if display == "inline":
                blocknode = False
            elif display == "block":
                blocknode = True
            else:
                blocknode = tag.blocknode

            sub = tokens[i + 1: pos]
            tokens[i:pos] = [
                Token(
                    type=Token.t_complex_tag,
                    children=sub,
                    tagname=tag.tagname,
                    blocknode=blocknode,
                    vlist=tokens[i].vlist,
                )
            ]
            pos = i + 1

        return pos

    def __call__(self, tokens, _):
        pos = 0
        self.stack = stack = [self.guard]
        get = self.name2tag.get

        while pos < len(tokens):
            token = tokens[pos]
            tag = get(token.rawtagname)
            if tag is None:
                pos += 1
                continue
            if token.type == Token.t_html_tag:
                pos = self.process_tag_stack(token, tag, tokens, pos, stack)
            else:
                pos = self.find_matching_tag(tokens, pos, tag, token)

        self.close_stack(1, tokens, pos)

    def process_tag_stack(self, token, tag, tokens, pos, stack):
        if token.tag_selfClosing:
            tokens[pos].type = Token.t_complex_tag
            tokens[pos].tagname = tokens[pos].rawtagname
            tokens[pos].rawtagname = None
            pos += 1
        else:
            if stack[-1][1].prio == tag.prio and not tag.nested:
                pos = self.close_stack(len(stack) - 1, tokens, pos)
                if tokens[pos] is not token:
                    raise ValueError("tokens[pos] is not t")
            stack.append((pos, tag))
            pos += 1
        return pos

    def find_matching_tag(self, tokens, pos, tag, token):
        if token.type != Token.t_html_tag_end:
            raise ValueError("Incorrect token type: %r" % token.type)
        # find a matching tag in the stack
        spos = self.find_in_stack(tag)
        if spos:
            pos = self.close_stack(spos, tokens, pos)
            if tokens[pos] is not token:
                raise ValueError("tokens[pos] is not t")
            del tokens[pos]
        else:
            pos += 1
        return pos
