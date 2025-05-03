#! /usr/bin/env py.test
import pytest

from mwlib.core import nshandling
from mwlib.network import siteinfo

siteinfo_de = siteinfo.get_siteinfo("de")
assert siteinfo_de, "cannot find german siteinfo"

benutzer_schmir = "Benutzer:Schmir"
cases = [
    ("User:Schmir", benutzer_schmir),
    ("user:Schmir", benutzer_schmir),
    ("benutzer:schmir", benutzer_schmir),
    (" user: schmir ", benutzer_schmir),
    ("___user___:___schmir  __", benutzer_schmir),
    ("User:SchmiR", "Benutzer:SchmiR"),
]
nshandler = nshandling.NsHandler(siteinfo_de)


@pytest.mark.parametrize("case", cases)
def test_fqname(case):
    fqname = nshandler.get_fqname(case[0])
    print(f"{case[0]!r} -> {fqname!r}")
    assert fqname == case[1]


cases = [
    ("user:schmir", benutzer_schmir),
    ("schmir", "Vorlage:Schmir"),
    (":schmir", "Schmir"),
]


@pytest.mark.parametrize("case", cases)
def test_fqname_defaultns(case):
    fqname = nshandler.get_fqname(case[0], 10)  # Vorlage
    print(f"{case[0]!r} -> {fqname!r}")
    assert fqname == case[1]


def test_redirect_matcher():
    m = nshandling.get_nshandler_for_lang("en").redirect_matcher
    assert (
        m("#REDIRECT [[Data structure#Active data structures]]") == "Data structure"
    ), "bad redirect"


def test_localized_redirect_matcher():
    m = nshandling.get_nshandler_for_lang("de").redirect_matcher
    data_structure = "Data structure"
    bad_redirect = "bad redirect"
    assert m("#REDIRECT [[Data structure]]") == data_structure, bad_redirect
    assert m("#WEITERLEITUNG [[Data structure]]") == data_structure, bad_redirect
