#! /usr/bin/env python

# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

from __future__ import absolute_import
from __future__ import print_function

import six
from pyparsing import (
    Literal,
    restOfLine,
    Word,
    nums,
    Group,
    ZeroOrMore,
    And,
    Suppress,
    LineStart,
    LineEnd,
    StringEnd,
    ParseException,
)


class Gob:
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def __repr__(self):
        return "<%s %r>" % (self.__class__.__name__, self.__dict__)


class Poly(Gob):
    pass


class Rect(Gob):
    pass


class Circle(Gob):
    pass


class Comment(Gob):
    pass


class Desc(Gob):
    pass


class Default(Gob):
    pass


class ImageMap(Gob):
    pass


def _make_poly(tokens):
    return Poly(caption=tokens[2].strip(), vertices=list(tokens[1]))


def _make_rect(tokens):
    return Rect(
        caption=tokens[-1].strip(), top_left=tuple(tokens[1]), bottom_right=tuple(tokens[2])
    )


def _make_comment(tokens):
    return Comment(comment=tokens[1])


def _make_circle(tokens):
    return Circle(caption=tokens[3].strip(), center=tokens[1], radius=tokens[2])


def _make_desc(tokens):
    return Desc(location=tokens[1])


def _make_imagemap(tokens):
    image = None
    for x in tokens:
        if isinstance(x, six.string_types):
            image = x
            break
    return ImageMap(entries=list(tokens), image=image)


comment = (Literal("#") + restOfLine).setParseAction(_make_comment)

integer = Word(nums).setParseAction(lambda s: int(s[0]))
integer_pair = (integer + integer).setParseAction(lambda x: tuple(x))

poly = Literal("poly") + Group(ZeroOrMore(integer_pair)) + restOfLine
poly = poly.setParseAction(_make_poly)

rect = Literal("rect") + integer_pair + integer_pair + restOfLine
rect = rect.setParseAction(_make_rect)

circle = Literal("circle") + integer_pair + integer + restOfLine
circle = circle.setParseAction(_make_circle)

desc = Literal("desc") + (
    Literal("top-right")
    | Literal("bottom-right")
    | Literal("bottom-left")
    | Literal("top-left")
    | Literal("none")
)
desc = desc.setParseAction(_make_desc)
default = Literal("default") + restOfLine
default.setParseAction(lambda t: Default(caption=t[1].strip()))


def _make_other(tokens):
    if not tokens[0]:
        return [None]
    return tokens


# we can't use restOfLine.setParseAction(_makeother) as that sets the
# parse action for any occurence of restOfLine


other = And([restOfLine]).setParseAction(_make_other)
line = (
    Suppress(LineStart())
    + (comment | poly | rect | circle | desc | default | other)
    + Suppress(LineEnd())
)
imagemap = ZeroOrMore(line) + StringEnd()
imagemap.setParseAction(_make_imagemap)


def image_map_from_string(s):
    # uhh. damn. can't get pyparsing to parse
    # commands, other lines (i.e. syntax errors strictly speaking)
    # and lines containing only whitespace...
    lines = []
    for x in s.split("\n"):
        x = x.strip()
        if x:
            lines.append(x)
    s = "\n".join(lines)

    try:
        return imagemap.parseString(s)[0]
    except ParseException as err:
        return ImageMap(entries=[], image=None)


def main():
    ex = """


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
    res = image_map_from_string(ex)
    for x in res.entries:
        print(x)


if __name__ == "__main__":
    main()
