#! /usr/bin/env python

"""used for debugging/testing"""

import sys
import time
import mwscan

d=unicode(open(sys.argv[1]).read(), 'utf-8')

stime=time.time()
r=mwscan.scan(d)
needed = time.time()-stime
for x in r:
    print r.repr(x)

print needed, len(d), len(r)



# stime=time.time()
# r=mwscan.compat_scan(d)
# needed = time.time()-stime

# print "COMPAT:", needed, len(d), len(r)


# #mwscan.dump_tokens(d,r)
# #print needed, len(d), len(r)
