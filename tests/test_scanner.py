#! /usr/bin/env py.test

from mwlib import scanner

def test_imagemap():
    s=u"""<imagemap>
Image:Foo.jpg|200px|picture of a foo
poly 131 45 213 41 210 110 127 109 [[Display]]
poly 104 126 105 171 269 162 267 124 [[Keyboard]]
rect 15 95 94 176   [[Foo type A]]
# A comment, this line is ignored
circle 57 57 20    [[Foo type B]]
desc bottom-left
</imagemap>"""
    tokens = scanner.tokenize('test', s)
    print "TOKENS:", tokens
    assert tokens[0] == ("IMAGEMAP", u"<imagemap>")
    assert tokens[-1] == ("IMAGEMAP", u"</imagemap>")
