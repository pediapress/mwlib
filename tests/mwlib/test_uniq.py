#! /usr/bin/env py.test

from mwlib.miscellaneous import uniq


def test_self_closing():
    u = uniq.Uniquifier()
    s = u.replace_tags(
        """
<ref />
----
<ref>
</ref>
"""
    )
    assert s.count("UNIQ") == 2


def test_empty_nowiki():
    u = uniq.Uniquifier()
    s = u.replace_tags("abc<nowiki></nowiki>def")
    assert "UNIQ" in s
    r = u.replace_uniq(s)
    assert r == "abcdef"


def test_space_in_closing_tag():
    u = uniq.Uniquifier()
    s = u.replace_tags("foo<ref>bar</ref >baz")
    assert "UNIQ" in s, "ref tag not recognized"


def test_comment():
    u = uniq.Uniquifier()

    def repl(txt, expected):
        res = u.replace_tags(txt)
        print((repr(txt), "->", repr(res)))
        assert res == expected

    repl("foo<!-- bla -->bar", "foobar")
    foo_bar = "foo\nbar"
    repl("foo\n<!-- bla -->\nbar", foo_bar)
    repl("foo\n<!-- bla -->bar", foo_bar)
    repl("foo<!-- bla -->\nbar", foo_bar)
