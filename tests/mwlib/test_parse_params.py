#! /usr/bin/env py.test

from mwlib.refine.util import parse_params


def test_display_none():
    r = parse_params("class=geo style=display:none")
    assert r == {"class": "geo", "style": {"display": "none"}}


def test_bgcolor_hashmark_no_doublequote():
    """http://code.pediapress.com/wiki/ticket/654"""
    r = parse_params("bgcolor=#ffffff")
    assert r == {"bgcolor": "#ffffff"}
