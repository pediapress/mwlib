#! /usr/bin/env python

try:
    import json
except ImportError:
    import simplejson as json

if __name__=='__main__':
    d=json.load(open("content.json"))
    for name, t in d['templates'].items():
        header = u" Template:%s" % (name,)
        print header.encode('utf-8')
        print t['content'].encode("utf-8")
