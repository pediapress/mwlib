#! /usr/bin/env py.test
from mwlib.templ import magics


def test_long_running_match():
    s = "<div " + " c" * 2000 + 'class="error">'
    assert magics.if_error_rx.match(s)


def test_long_running_no_match():
    s = "<div " + " c" * 2000 + 'class="erro">'
    assert not magics.if_error_rx.match(s)


def test_long_running_match_newline():
    s = "<div " + " c" * 1000 + "\n" + " c" * 1000 + 'class="error">'
    assert magics.if_error_rx.match(s)
