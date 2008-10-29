#! /usr/bin/env python

import sys
import time
from mwlib import expr

e = []
for x in sys.stdin:
    e.append(eval(x))

print "have %s expressions" % len(e)
stime=time.time()
for x in e:
    expr.expr(u"1+2")
print "needed", time.time()-stime
