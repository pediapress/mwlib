#! /usr/bin/env py.test

from mwlib import utoken as mwscan


def test_resolve_symbolic_entity():
    assert mwscan.resolve_entity(u"&amp;")==u"&", "bad result"

def test_resolve_numeric_entity():    
    assert mwscan.resolve_entity(u"&#32;")==u' ', "expected space"

def test_resolve_hex_entity():    
    assert mwscan.resolve_entity(u"&#x20;")==u' ', "expected space"

def test_resolve_entity_out_of_range():
    s="&#x1000000;"
    assert mwscan.resolve_entity(s)==s, "should expand to same string"
    
def test_url():
    s=mwscan.scan("http://tools.wikimedia.de/~magnus/geo/geohack.php?language=de&params=50_0_0_N_8_16_16_E_type:city(190934)_region:DE-RP")
    print s
    assert len(s)==1, "expected one url"

def _check_table_markup(s):
    toks = [t[0] for t in mwscan.scan(s)]
    print "TOKENS:",toks
    assert mwscan.token.t_begin_table not in toks, "should not contain table markup"
    assert mwscan.token.t_end_table not in toks, "should not contain table markup"
    
def test_table_bol_begin_code():
    _check_table_markup("<code>{|</code>")
    
def test_table_bol_begin():
    _check_table_markup("foo {| bar")

def test_table_bol_end_code():
    _check_table_markup("<code>|}</code>")
    
def test_table_bol_end():
    _check_table_markup("foo |} bar")
    
    
