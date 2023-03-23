#! /usr/bin/env py.test

from mwlib.templ import pp


def preprocess(s, expected, included=True):
    res = pp.preprocess(s, included=included)
    print(f"preprocess({s!r}) -> {res!r}")
    if expected is not None:
        assert res == expected, "bad preprocess result"


def test_includeonly_included():
    def d(s, e):
        return preprocess(s, e, included=False)

    d(
        "foo<includeonly>bar baz\n\n\nbla</includeonly>123<includeonly>foo bar</includeonly>456",
        "foo123456",
    )
    d("foo<includeonly>bar baz\n\n\nbla", "foo")
    d("foo<ONLYINCLUDE>123</onlyinclude>456", "foo123456")
    d("foo<NOINCLUDE>123</noinclude>456", "foo123456")


def test_noinclude_ws():
    preprocess("<noinclude>foo</noinclude>", "", True)
    preprocess("<noinclude >foo</noinclude>", "", True)
    preprocess("<noinclude sadf asdf asd>foo</noinclude>", "", True)
    preprocess("<noinclude\n\t>foo</noinclude>", "", True)
    preprocess("<noincludetypo>foo</noinclude>", "<noincludetypo>foo</noinclude>", True)


def test_includeonly_ws():
    preprocess("<includeonly>foo</includeonly>", "", False)
    preprocess("<includeonly >foo</includeonly>", "", False)
    preprocess("<includeonly\n>foo</includeonly>", "", False)


def test_remove_not_included_ws():
    preprocess("<noinclude>foo", "foo", False)
    preprocess("<noinclude >foo", "foo", False)
    preprocess("<noinclude\n>foo", "foo", False)
    preprocess("<noinclude\nid=5 >foo", "foo", False)
    preprocess("<onlyinclude\nid=5 >foo", "foo", False)
