#! /usr/bin/env python
import sys
from mwlib import lang, mwapidb
import pprint

def main():

    languages = sys.argv[1:]
    if not languages:
        languages = list(lang.languages)
        languages.sort()
    langdata = {}
    for l in languages:
        w=mwapidb.APIHelper("http://%s.wikipedia.org/w" % l)
        res = w.query(meta='siteinfo', siprop='general|namespaces|namespacealiases|magicwords|interwikimap')
        if res is not None:
            
            langdata[l] = res["query"]
            f=open("siteinfo_%s.py" % l, "wb")
            f.write("""
# automatically genereted by sandbox/fetch-langdata.py

siteinfo = \\
""")
            pprint.pprint(res["query"], f)
            f.write("""

from mwlib.siteinfo._registry import register
register(%r, siteinfo)
""" % l)
if __name__=="__main__":
    main()
    
