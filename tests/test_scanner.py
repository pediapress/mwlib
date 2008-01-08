#! /usr/bin/env py.test

from mwlib import scanner
def tokenize(s):
    tokens = scanner.tokenize(s, "test")
    print "TOKENIZE", repr(s)
    print "  ---->", tokens
    return tokens


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
    tokens = tokenize(s)
    print "TOKENS:", tokens
    assert tokens[0] == ("IMAGEMAP", u"<imagemap>")
    assert tokens[-1] == ("IMAGEMAP", u"</imagemap>")

def test_fucked_up_html_tags():
    """http://code.pediapress.com/wiki/ticket/25"""

    s='<div };">'
    tokens=tokenize(s)
    t=tokens[0]
    print "T:", t
    assert isinstance(t[0], scanner.TagToken)
    assert t[0].t == 'div'
    assert t[1]==s
