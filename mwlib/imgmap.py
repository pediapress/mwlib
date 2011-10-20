#! /usr/bin/env python

# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

from pyparsing import (Literal, restOfLine, Word, nums, Group, 
                       ZeroOrMore, OneOrMore, And, Suppress, LineStart, 
                       LineEnd, StringEnd, ParseException, Optional, White)

class gob(object): 
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def __repr__(self):
        return "<%s %r>" % (self.__class__.__name__, self.__dict__)

class Poly(gob): pass
class Rect(gob): pass
class Circle(gob): pass
class Comment(gob): pass
class Desc(gob): pass
class Default(gob): pass
class ImageMap(gob): pass

def _makepoly(tokens):
    return Poly(caption=tokens[2].strip(), vertices=list(tokens[1]))

def _makerect(tokens):
    return Rect(caption=tokens[-1].strip(), top_left=tuple(tokens[1]), bottom_right=tuple(tokens[2]))

def _makecomment(tokens):
    return Comment(comment=tokens[1])

def _makecircle(tokens):
    return Circle(caption=tokens[3].strip(), center=tokens[1], radius=tokens[2])

def _makedesc(tokens):
    return Desc(location=tokens[1])

def _makeimagemap(tokens):
    image = None
    for x in tokens:
        if isinstance(x, basestring):
            image = x
            break
    return ImageMap(entries=list(tokens), image=image)

        
comment = (Literal('#')+restOfLine).setParseAction(_makecomment)

integer = Word(nums).setParseAction(lambda s: int(s[0]))
integer_pair = (integer+integer).setParseAction(lambda x: tuple(x))

poly = Literal("poly")+Group(ZeroOrMore(integer_pair))+restOfLine
poly = poly.setParseAction(_makepoly)

rect = Literal("rect")+integer_pair+integer_pair+restOfLine
rect = rect.setParseAction(_makerect)

circle = Literal("circle")+integer_pair+integer+restOfLine
circle = circle.setParseAction(_makecircle)

desc = Literal("desc") + (Literal("top-right")
                          |Literal("bottom-right")
                          |Literal("bottom-left")
                          |Literal("top-left")
                          |Literal("none"))
desc = desc.setParseAction(_makedesc)
default = Literal("default")+restOfLine
default.setParseAction(lambda t: Default(caption=t[1].strip()))


def _makeother(tokens):
    if not tokens[0]:
        return [None]
    return tokens

# we can't use restOfLine.setParseAction(_makeother) as that sets the 
# parse action for any occurence of restOfLine

other = And([restOfLine]).setParseAction(_makeother)
line = Suppress(LineStart()) + (comment | poly | rect | circle | desc | default | other) + Suppress(LineEnd())
imagemap = ZeroOrMore(line) + StringEnd()
imagemap.setParseAction(_makeimagemap)

def ImageMapFromString(s):
    # uhh. damn. can't get pyparsing to parse
    # commands, other lines (i.e. syntax errors strictly speaking)
    # and lines containing only whitespace...
    lines = []
    for x in s.split("\n"):
        x=x.strip()
        if x:
            lines.append(x)
    s="\n".join(lines)

    try:
        return imagemap.parseString(s)[0]
    except ParseException, err:
        return ImageMap(entries=[], image=None)

def main():
    ex="""


Image:Foo.jpg|200px|picture of a foo
poly 131 45 213 41 210 110 127 109 [[Display]]
poly 104 126 105 171 269 162 267 124 [[Keyboard]]
rect 15 95 94 176   [[Foo type A]]
# A comment, this line is ignored
circle 57 57 20    [[Foo type B]]
desc bottom-left
default [[Mainz]]
---dfg-sdfg--sdfg
blubb
"""
    res = ImageMapFromString(ex)
    for x in res.entries:
        print x

if __name__=='__main__':
    main()
