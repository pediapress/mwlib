#! /usr/bin/env py.test

import copy
from mwlib.templ import nodes, parser
from mwlib.siteinfo import get_siteinfo

si = copy.deepcopy(get_siteinfo("en"))
del si["magicwords"]

def test_aliasmap_no_magicwords():
    parser.aliasmap(si)


def test_parser_no_magicwords():
    p = parser.Parser(u"some text", siteinfo=si)
    p.parse()
