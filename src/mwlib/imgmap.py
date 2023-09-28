#! /usr/bin/env python

# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.




import six
from pyparsing import (
    And,
    Group,
    LineEnd,
    LineStart,
    Literal,
    ParseException,
    StringEnd,
    Suppress,
    Word,
    ZeroOrMore,
    nums,
    restOfLine,
)


class Gob:
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.__dict__!r}>"


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
        caption=tokens[-1].strip(), top_left=tuple(tokens[1]),
        bottom_right=tuple(tokens[2])
    )


def _make_comment(tokens):
    return Comment(comment=tokens[1])


def _make_circle(tokens):
    return Circle(caption=tokens[3].strip(), center=tokens[1], radius=tokens[2])


def _make_desc(tokens):
    return Desc(location=tokens[1])


def _make_imagemap(tokens):
    image = None
    for token in tokens:
        if isinstance(token, six.string_types):
            image = token
            break
    return ImageMap(entries=list(tokens), image=image)


comment = (Literal("#") + restOfLine).setParseAction(_make_comment)

INTEGER = Word(nums).setParseAction(lambda single_number: int(single_number[0]))
INTEGER_PAIR = (INTEGER + INTEGER).setParseAction(lambda pair_of_numbers: tuple(pair_of_numbers))

POLY = Literal("poly") + Group(ZeroOrMore(INTEGER_PAIR)) + restOfLine
POLY = POLY.setParseAction(_make_poly)

RECT = Literal("rect") + INTEGER_PAIR + INTEGER_PAIR + restOfLine
RECT = RECT.setParseAction(_make_rect)

CIRCLE = Literal("circle") + INTEGER_PAIR + INTEGER + restOfLine
CIRCLE = CIRCLE.setParseAction(_make_circle)

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


OTHER = And([restOfLine]).setParseAction(_make_other)
line = (
    Suppress(LineStart())
    + (comment | POLY | RECT | CIRCLE | desc | default | OTHER)
    + Suppress(LineEnd())
)
imagemap = ZeroOrMore(line) + StringEnd()
imagemap.setParseAction(_make_imagemap)


def image_map_from_string(input_string):
    # uhh. damn. can't get pyparsing to parse
    # commands, other lines (i.e. syntax errors strictly speaking)
    # and lines containing only whitespace...
    lines = []
    for segment in input_string.split("\n"):
        segment = segment.strip()
        if segment:
            lines.append(segment)
    input_string = "\n".join(lines)

    try:
        return imagemap.parseString(input_string)[0]
    except ParseException:
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
    for entry in res.entries:
        print(entry)


if __name__ == "__main__":
    main()
