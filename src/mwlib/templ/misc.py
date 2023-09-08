# Copyright (c) 2007-2009 PediaPress GmbH
# See README.md for additional licensing information.

from mwlib.siteinfo import get_siteinfo
from mwlib.templ import evaluate


class Page:
    def __init__(self, rawtext):
        self.rawtext = rawtext


class DictDB:
    """wikidb implementation used for testing"""

    def __init__(self, *args, **kw):
        if args:
            (self.d,) = args
        else:
            self.d = {}

        self.d.update(kw)

        normd = {}
        for k, v in self.d.items():
            normd[k.lower().replace(" ", "_")] = v
        self.d = normd

        self.siteinfo = get_siteinfo("de")

    def normalize_and_get_page(self, title, defaultns=0):
        return Page(self.d.get(title.lower().replace(" ", "_"), ""))

    def get_siteinfo(self):
        return self.siteinfo


def expand_str(s, expected=None, wikidb=None, pagename="thispage"):
    """debug function. expand templates in string s"""
    db = wikidb if wikidb else DictDB({"a": s})

    te = evaluate.Expander(s, pagename=pagename, wikidb=db)
    res = te.expandTemplates()
    print(f"EXPAND: {s!r} -> {res!r}")
    if expected is not None and res != expected:
        raise AssertionError(f"expected {expected!r}, got {res!r}")
    return res
