#! /usr/bin/env python

import os
import urllib

urls = open("urls.txt").read().split()
for x in urls:
    path = x[len("http://"):]
    if os.path.exists(path):
        continue
    
    print "fetching", x,
    data = urllib.urlopen(x).read()
    dn = os.path.dirname(path)
    if not os.path.exists(dn):
        os.makedirs(dn)
    open(path, "wb").write(data)
    print "%s bytes" % (len(data), )
    
    
