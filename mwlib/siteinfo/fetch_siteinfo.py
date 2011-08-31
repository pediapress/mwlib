#! /usr/bin/env python

import sys
import urllib
try:
    import simplejson as json
except ImportError:
    import json

def fetch(lang):
    url = 'http://%s.wikipedia.org/w/api.php?action=query&meta=siteinfo&siprop=general|namespaces|namespacealiases|magicwords|interwikimap&format=json' % lang
    print 'fetching %r' % url
    data = urllib.urlopen(url).read()
    fn = 'siteinfo-%s.json' % lang
    print 'writing %r' % fn
    data = json.loads(data)['query']
    json.dump(data, open(fn, 'wb'), indent=4, sort_keys=True)

def main(argv):
    languages = argv[1:]
    if not languages:
        languages = "de en es fr it ja nl no pl pt simple sv".split()

    for lang in languages:
        fetch(lang.lower())

if __name__ == '__main__':
    main(sys.argv)
