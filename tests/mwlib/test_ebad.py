#! /usr/bin/env py.test
from mwlib.refine import core
from mwlib.token.utoken import Token as T


def test_ebad_in_text():
    txt = T.join_as_text(core.parse_txt("foo\uebadbar"))
    assert txt == "foobar", "\uebad should be stripped"
