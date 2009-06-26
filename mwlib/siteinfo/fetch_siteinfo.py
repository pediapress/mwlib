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
    if len(argv) < 2:
        sys.exit('Usage: %s LANGUAGE1 [LANGUAGE2 [...]]' % argv[0])

    for lang in argv[1:]:
        fetch(lang.lower())

if __name__ == '__main__':
    main(sys.argv)
