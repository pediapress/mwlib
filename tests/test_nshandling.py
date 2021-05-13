#! /usr/bin/env py.test
import pytest

from mwlib import nshandling, siteinfo

siteinfo_de = siteinfo.get_siteinfo("de")
assert siteinfo_de, "cannot find german siteinfo"


cases = [
    ("User:Schmir", "Benutzer:Schmir"),
    ("user:Schmir", "Benutzer:Schmir"),
    ("benutzer:schmir", "Benutzer:Schmir"),
    (" user: schmir ", "Benutzer:Schmir"),
    ("___user___:___schmir  __", "Benutzer:Schmir"),
    ("User:SchmiR", "Benutzer:SchmiR"),
]
nshandler = nshandling.nshandler(siteinfo_de)


@pytest.mark.parametrize("case", cases)
def test_fqname(case):
    fqname = nshandler.get_fqname(case[0])
    print("%r -> %r" % (case[0], fqname))
    assert fqname == case[1]


cases = [
    ("user:schmir", "Benutzer:Schmir"),
    ("schmir", "Vorlage:Schmir"),
    (":schmir", "Schmir"),
]


@pytest.mark.parametrize("case", cases)
def test_fqname_defaultns(case):
    fqname = nshandler.get_fqname(case[0], 10)  # Vorlage
    print("%r -> %r" % (case[0], fqname))
    assert fqname == case[1]


def test_redirect_matcher():
    m = nshandling.get_nshandler_for_lang("en").redirect_matcher
    assert (
        m("#REDIRECT [[Data structure#Active data structures]]") == "Data structure"
    ), "bad redirect"


def test_localized_redirect_matcher():
    m = nshandling.get_nshandler_for_lang("de").redirect_matcher
    assert m("#REDIRECT [[Data structure]]") == "Data structure", "bad redirect"
    assert m("#WEITERLEITUNG [[Data structure]]") == "Data structure", "bad redirect"
