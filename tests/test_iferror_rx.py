#! /usr/bin/env py.test

from mwlib.templ import magics


def test_long_running_match(alarm):
    s = '<div ' + ' c' * 2000 + 'class="error">'
    alarm(0.01)
    assert magics.iferror_rx.match(s)


def test_long_running_no_match(alarm):
    s = '<div ' + ' c' * 2000 + 'class="erro">'
    alarm(0.01)
    assert not magics.iferror_rx.match(s)


def test_long_running_match_newline(alarm):
    s = '<div ' + ' c' * 1000 + '\n' + ' c' * 1000 + 'class="error">'
    alarm(0.01)
    assert magics.iferror_rx.match(s)
