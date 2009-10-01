#! /usr/bin/env py.test

from mwlib import nshandling, siteinfo
siteinfo_de = siteinfo.get_siteinfo("de")
assert siteinfo_de, "cannot find german siteinfo"

def test_fqname():
    def get_fqname(name, expected):
        fqname = nshandler.get_fqname(name)
        print "%r -> %r" % (name, fqname)
        assert fqname==expected
        
    nshandler = nshandling.nshandler(siteinfo_de)

    d = get_fqname
    e = "Benutzer:Schmir"
    
    yield d, "User:Schmir", e
    yield d, "user:Schmir", e
    yield d, "benutzer:schmir", e
    yield d, " user: schmir ", e
    yield d, "___user___:___schmir  __", e
    yield d, "User:SchmiR", "Benutzer:SchmiR"
    
def test_fqname_defaultns():
    def get_fqname(name, expected):
        fqname = nshandler.get_fqname(name, 10) # Vorlage
        print "%r -> %r" % (name, fqname)
        assert fqname==expected
    
    nshandler = nshandling.nshandler(siteinfo_de)
    d = get_fqname

    yield d, "user:schmir", "Benutzer:Schmir"
    yield d, "schmir", "Vorlage:Schmir"
    yield d, ":schmir", "Schmir"

def test_redirect_matcher():
    m = nshandling.get_nshandler_for_lang ("en").redirect_matcher
    assert m("#REDIRECT [[Data structure#Active data structures]]")=="Data structure",  "bad redirect"
    
    
