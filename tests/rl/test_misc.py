#! /usr/bin/env py.test

# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.

from mwlib.writers.rl.writer import RlWriter


def writer():

    r = RlWriter(test_mode=True)
    return r


def test_fake_hyphenate():
    txt = "1. dont break this"
    r = writer()
    res = r.renderText(txt, break_long=True)
    assert res.find("<font") == -1

    txt = "1.break this please"
    res = r.renderText(txt, break_long=True)
    assert res.find("<font") == 2

    for break_char in ["/", ".", "+", "-", "_", "?"]:
        txt = "bla%sblub" % break_char  # add fake hypenation
        res = r.renderText(txt, break_long=True)
        assert res.find("<font") == 4

        txt = "bla%s blub" % break_char  # leave untouched
        res = r.renderText(txt, break_long=True)
        assert res.find("<font") == -1
