#! /usr/bin/env python

try:
    import json
except ImportError:
    import simplejson as json

def exdict(d, name):
    for name, t in d.items():
        header = u" Template:%s" % (name,)
        print header.encode('utf-8')
        print t['content'].encode("utf-8")


def main():
    d=json.load(open("content.json"))
    exdict(d['templates'], 'Template')
    exdict(d['articles'], 'Article')
    
if __name__=='__main__':
    main()
    
