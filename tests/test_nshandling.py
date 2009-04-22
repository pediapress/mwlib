#! /usr/bin/env py.test

from mwlib import nshandling, siteinfo

def test_fqname():
    def get_fqname(name, expected):
        fqname = nsmapper.get_fqname(name)
        print "%r -> %r" % (name, fqname)
        assert fqname==expected
        
    siteinfo_de = siteinfo.get_siteinfo("de")
    assert siteinfo_de
    nsmapper = nshandling.nsmapper(siteinfo_de)

    d = get_fqname
    e = "Benutzer:Schmir"
    
    yield d, "User:Schmir", e
    yield d, "user:Schmir", e
    yield d, "benutzer:schmir", e
    yield d, " user: schmir ", e
    yield d, "___user___:___schmir  __", e
    
