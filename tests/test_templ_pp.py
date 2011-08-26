#! /usr/bin/env py.test

from mwlib.templ import pp


def preprocess(s, expected, included=True):
    res = pp.preprocess(s, included=included)
    print "preprocess(%r) -> %r" % (s, res)
    if expected is not None:
        assert res == expected, "bad preprocess result"


def test_includeonly_included():
    d = lambda s, e: preprocess(s, e, included=False)
    yield d, "foo<includeonly>bar baz\n\n\nbla</includeonly>123<includeonly>foo bar</includeonly>456", "foo123456"
    yield d, "foo<includeonly>bar baz\n\n\nbla", "foo"
    yield d, "foo<ONLYINCLUDE>123</onlyinclude>456", "foo123456"
    yield d, "foo<NOINCLUDE>123</noinclude>456", "foo123456"


def test_noinclude_ws():
    yield preprocess, "<noinclude>foo</noinclude>", "", True
    yield preprocess, "<noinclude >foo</noinclude>", "", True
    yield preprocess, "<noinclude sadf asdf asd>foo</noinclude>", "", True
    yield preprocess, "<noinclude\n\t>foo</noinclude>", "", True

    yield preprocess, "<noincludetypo>foo</noinclude>", "<noincludetypo>foo</noinclude>", True

def test_includeonly_ws():
    yield preprocess, "<includeonly>foo</includeonly>", "", False
    yield preprocess, "<includeonly >foo</includeonly>", "", False
    yield preprocess, "<includeonly\n>foo</includeonly>", "", False


def test_remove_not_included_ws():
    yield preprocess, "<noinclude>foo", "foo", False
    yield preprocess, "<noinclude >foo", "foo", False
    yield preprocess, "<noinclude\n>foo", "foo", False
    yield preprocess, "<noinclude\nid=5 >foo", "foo", False

    yield preprocess, "<onlyinclude\nid=5 >foo", "foo", False

