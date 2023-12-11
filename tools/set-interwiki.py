#! /usr/bin/env python

"""usage: set-interwiki SITEINFO.JSON | mysql WIKIDB
    create entries in interwiki table from existing siteinfo
    (see http://www.mediawiki.org/wiki/Manual:Interwiki)
"""

import sys
try:
    import simplejson as json
except ImportError:
    import json


def main():
    if len(sys.argv) != 2:
        import __main__
        print(__main__.__doc__)
        sys.exit(10)

    siteinfo = json.load(open(sys.argv[1]))
    for e in siteinfo["interwikimap"]:
        msg = "INSERT INTO interwiki SET iw_prefix='{}', iw_url='{}', iw_local=1, iw_trans=0 ;".format(
            e["prefix"], e["url"])
        print(msg.encode("utf-8"))


if __name__ == "__main__":
    main()
