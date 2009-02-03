#! /usr/bin/env py.test

from mwlib.templ import pp


def preprocess(s, expected, included=True):
    res = pp.preprocess(s, included=included)
    
    print "preprocess(%r) -> %r" % (s, res)
    if expected:
        assert res==expected, "bad preprocess result"
        
def test_includeonly_included():
    d = lambda s, e: preprocess(s, e, included=False)
    yield d, "foo<includeonly>bar baz\n\n\nbla</includeonly>123<includeonly>foo bar</includeonly>456", "foo123456"
    yield d, "foo<includeonly>bar baz\n\n\nbla", "foo"
    yield d, "foo<ONLYINCLUDE>123</onlyinclude>456", "foo123456"
    yield d, "foo<NOINCLUDE>123</noinclude>456", "foo123456"
