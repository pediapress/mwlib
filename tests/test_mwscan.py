#! /usr/bin/env py.test

from mwlib import mwscan


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
    s.dump()
    assert len(s)==1, "expected one url"

def test_url2():
    s=mwscan.scan('[http://www.computer.org/portal/site/computer/menuitem.5d61c1d591162e4b0ef1bd108bcd45f3/index.jsp?&pName=computer_level1_article&TheCat=1055&path=computer/homepage/Feb07&file=howthings.xml&xsl=article.xsl&;jsessionid=G10s8pkpkP1K0Lk07bXx5dR0mXLSj8hXdnLDN5Kjj5GZTJtTTLZ0!1592783441 How GPUs work]')
    print s.toks
    assert s.rawtext(s.toks[1]) == u' How GPUs work'

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

def test_tagtoken_repr():
    t=mwscan.TagToken(unichr(180))
    repr(t)
    
def test_endtagtoken_repr():
    t=mwscan.EndTagToken(unichr(180))
    repr(t)
    
    
