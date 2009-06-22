#! /usr/bin/env py.test

from mwlib import utoken, uniq

def test_self_closing():
    u=uniq.Uniquifier()
    s=u.replace_tags("""
<ref />
----
<ref>
</ref>
""")
    assert s.count("UNIQ")==2
    
def test_empty_nowiki():
    u=uniq.Uniquifier()
    s=u.replace_tags("abc<nowiki></nowiki>def")
    assert 'UNIQ' in s
    r=u.replace_uniq(s)
    assert r=="abcdef"

def test_space_in_closing_tag():
    u=uniq.Uniquifier()
    s=u.replace_tags("foo<ref>bar</ref >baz")
    assert "UNIQ" in s, "ref tag not recognized"
    
def test_comment():
    u = uniq.Uniquifier()
    def repl(txt, expected):
        res = u.replace_tags(txt)
        print repr(txt),  "->",  repr(res)
        assert res == expected

    yield repl,  "foo<!-- bla -->bar",  "foobar"
    yield repl,  "foo\n<!-- bla -->\nbar",  "foo\nbar"
    yield repl,  "foo\n<!-- bla -->bar",  "foo\nbar"
    yield repl,  "foo<!-- bla -->\nbar",  "foo\nbar"
