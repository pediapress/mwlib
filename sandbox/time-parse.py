#! /usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import time

from mwlib.tree import advtree

s = unicode(open(sys.argv[1], "rb").read(), "utf-8")

from mwlib import uparser, treecleaner
from mwlib.refine import compat

stime = time.time()
r = compat.parse_txt(s)
print "parse:", time.time() - stime

stime = time.time()
advtree.build_advanced_tree(r)
print "tree", time.time() - stime

stime = time.time()
tc = treecleaner.TreeCleaner(r)
tc.clean_all()
print "clean:", time.time() - stime
