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
            (self.data_dict,) = args
        else:
            self.data_dict = {}

        self.data_dict.update(kw)

        normd = {}
        for k, val in self.data_dict.items():
            normd[k.lower().replace(" ", "_")] = val
        self.data_dict = normd

        self.siteinfo = get_siteinfo("de")

    def normalize_and_get_page(self, title, defaultns=0):
        return Page(self.data_dict.get(title.lower().replace(" ", "_"), ""))

    def get_siteinfo(self):
        return self.siteinfo


def expand_str(input_string, expected=None, wikidb=None, pagename="thispage"):
    """debug function. expand templates in string s"""
    wiki_db = wikidb if wikidb else DictDB({"a": input_string})

    template_expander = evaluate.Expander(input_string, pagename=pagename, wikidb=wiki_db)
    res = template_expander.expandTemplates()
    print(f"EXPAND: {input_string!r} -> {res!r}")
    if expected is not None and res != expected:
        raise AssertionError(f"expected {expected!r}, got {res!r}")
    return res
