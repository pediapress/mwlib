#! /usr/bin/env py.test
# -*- coding: utf-8 -*-

from mwlib.parser import parseParams

def test_display_none():
    r=parseParams("class=geo style=display:none")
    assert r=={'class': 'geo', 'style': {'display': 'none'}}
 
