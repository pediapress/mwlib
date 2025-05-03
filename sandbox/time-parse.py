#! /usr/bin/env python
import sys
import time

from mwlib import treecleaner, uparser
from mwlib.parser import advtree
from mwlib.parser.refine import compat

with open(sys.argv[1], encoding="utf-8") as f:
    s = f.read()

stime = time.time()
r = compat.parse_txt(s)
print("parse:", time.time() - stime)

stime = time.time()
advtree.build_advanced_tree(r)
print("tree", time.time() - stime)

stime = time.time()
tc = treecleaner.TreeCleaner(r)
tc.clean_all()
print("clean:", time.time() - stime)
