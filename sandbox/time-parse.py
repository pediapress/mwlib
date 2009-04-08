#! /usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import time

s = unicode(open(sys.argv[1], "rb").read(), "utf-8")

from mwlib import uparser, advtree, treecleaner
from mwlib.refine import compat

stime = time.time()
r = compat.parse_txt(s)
print "parse:", time.time()-stime

stime = time.time()
advtree.buildAdvancedTree(r)
print "tree", time.time()-stime

stime = time.time()
tc = treecleaner.TreeCleaner(r)
tc.cleanAll()
print "clean:", time.time()-stime
