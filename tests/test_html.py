#!/usr/bin/env py.test
# -*- coding: utf-8 -*-

import StringIO

from mwlib import uparser, htmlwriter, dummydb

def gen_html(name, raw):
    out = StringIO.StringIO()
    p = uparser.parseString(name, raw=raw, wikidb=dummydb.DummyDB())
    print list(p.allchildren())
    w = htmlwriter.HTMLWriter(out)
    w.write(p)
    return out.getvalue()

def test_table_style():
    html = gen_html('test', '{| class="toccolours" '
            'style="clear:both; margin:1.5em auto; text-align:center;" |}')
    assert html.find("'text-align':'center'") < 0
    assert html.find('text-align:center') > 0

