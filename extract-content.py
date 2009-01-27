#! /usr/bin/env python

import sys

try:
    import json
except ImportError:
    import simplejson as json

def exdict(d, ns):
    for name, t in d.items():
        if t['content'] is None:
            sys.stderr.write("no such %s:%s\n" % (ns, name))
            continue
        header = u" %s:%s" % (ns, name)
        print header.encode('utf-8')
        print t['content'].encode("utf-8")


def main():
    d=json.load(open("content.json"))
    exdict(d['templates'], 'Template')
    exdict(d['articles'], 'Article')
    
if __name__=='__main__':
    main()
    
