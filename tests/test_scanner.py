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
    assert tokens[0] == (scanner.TagToken("imagemap"), u"<imagemap>")
    assert tokens[-1] == (scanner.EndTagToken("imagemap"), u"</imagemap>")

def test_fucked_up_html_tags():
    """http://code.pediapress.com/wiki/ticket/25"""

    s='<div };">'
    tokens=tokenize(s)
    t=tokens[0]
    print "T:", t
    assert isinstance(t[0], scanner.TagToken)
    assert t[0].t == 'div'
    assert t[1]==s

def test_nowiki_gt_lt():
    tokenize("<nowiki>< lt</nowiki>")
    tokenize("<nowiki>> gt</nowiki>")

    
def test_only_ws_after_endsection():
    tokens = tokenize("= foo = bar")
    token_types = [x[0] for x in tokens]

    assert 'ENDSECTION' not in token_types, "not an endsection"

def test_endsection_whitespace():
    tokens = tokenize("= foo =  ")
    token_types = [x[0] for x in tokens]
    
    assert ('ENDSECTION', '=  ') in tokens, "missing endsection token"

def test_endsection():
    tokens = tokenize("= foo =")
    token_types = [x[0] for x in tokens]
    
    assert ('ENDSECTION', '=') in tokens, "missing endsection token"

def test_negative_tablecount():
    """test for http://code.pediapress.com/wiki/ticket/73"""
    
    s=r"""{|
|-
|<math>|}</math>
|}

{|
|-
| foobar
|}
"""
    tokens=scanner.tokenize(s)
    count = tokens.count(("ROW", "|-"))
    assert count==2, "expected two row symbols. got %s" % (count,)

def test_preformatted_pipe():
    """http://code.pediapress.com/wiki/ticket/92"""
    tokens=scanner.tokenize("   |foo")
    assert tokens==[('PRE', ' '), ('TEXT', '  '), ('SPECIAL', '|'), ('TEXT', 'foo')]
    
def test_url_with_at_signs():
    """http://code.pediapress.com/wiki/ticket/285"""
    
    tokens = scanner.tokenize('http://example.com/foo@bar@baz')
    assert len(tokens) == 1
    assert tokens[0] == ('URL', 'http://example.com/foo@bar@baz')


