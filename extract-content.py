#! /usr/bin/env python

import sys
from mwlib import namespace

try:
    import json
except ImportError:
    import simplejson as json

def exdict(d, default_ns):
    
    for name, t in d.items():
        ns, partial, full = namespace.splitname(name, default_ns)
        
        if t['content'] is None:
            sys.stderr.write("no such %r\n" % full)
            continue
        header = u" %s" % full
        print header.encode('utf-8')
        print t['content'].encode("utf-8")


def main():
    d=json.load(open("content.json"))
    exdict(d['templates'], namespace.NS_TEMPLATE)
    exdict(d['articles'], namespace.NS_MAIN)
    
if __name__=='__main__':
    main()
    
