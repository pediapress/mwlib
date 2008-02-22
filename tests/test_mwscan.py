#! /usr/bin/env py.test

from mwlib import mwscan


def test_resolve_symbolic_entity():
    assert mwscan.resolve_entity(u"&amp;")==u"&", "bad result"

def test_resolve_numeric_entity():    
    assert mwscan.resolve_entity(u"&#32;")==u' '

def test_resolve_hex_entity():    
    assert mwscan.resolve_entity(u"&#x20;")==u' '
