#! /usr/bin/env py.test

from mwlib import dummydb, parser, expander, uparser
from mwlib.expander import DictDB

parse = uparser.simpleparse

def test_simple_table():
    r=parse("""{|
|-
| A || B
|-
| C || D
|}""")
    table = r.find(parser.Table)[0]
    print "TABLE:", table
    
    assert len(table.children)==2, "expected two rows"
    for x in table.children:
        assert len(x.children)==2, "expected 2 cells"

