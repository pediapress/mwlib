#! /usr/bin/env py.test
# -*- coding: utf-8 -*-

from mwlib.refine.util import parseParams

def test_display_none():
    r=parseParams("class=geo style=display:none")
    assert r=={'class': 'geo', 'style': {'display': 'none'}}

def test_bgcolor_hashmark_no_doublequote():
    """http://code.pediapress.com/wiki/ticket/654"""
    r=parseParams("bgcolor=#ffffff")
    assert r==dict(bgcolor="#ffffff")
    
