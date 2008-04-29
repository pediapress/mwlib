#! /usr/bin/env python

from pprint import pprint
import sys

from mwlib.mwapidb import APIHelper

class LicenseFetcher(object):
    api_helper = APIHelper('http://commons.wikimedia.org/w/')
    category_title = u'Category:License tags attribution'
    nonfree_licenses = ()
    
    def getLicenses(self):
        result = self.api_helper.query(
            list='categorymembers',
            cmtitle=self.category_title,
            cmprop='title',
            cmlimit=500,
            cmnamespace=10,
        )
        members = result['categorymembers']
        return [cm['title'].split(':', 1)[-1] for cm in members]
    
    def isFree(self, license):
        return license.lower() not in self.nonfree_licenses
    
    def getFreeLicenses(self):
        return [license for license in self.getLicenses() if self.isFree(license)]
    

def main(argv=None):
    if argv is None:
        argv = sys.argv
    
    if len(argv) not in (1, 2):
        sys.exit('Usage: %s [OUTPUTFILE]' % argv[0])
    
    lf = LicenseFetcher()
    if len(argv) == 2:
        lower2normal = {}
        for license in lf.getFreeLicenses():
            lower2normal[license.lower()] = license
        
        f = open(argv[1], 'wb')
        f.write('''#! /usr/bin/env python

"""Mapping of lower-cased template names of licenses to their normalized name.
This file has been automatically generated with tools/get_license_templates.py
"""

lower2normal = ''')
        pprint(lower2normal, f)
    else:
        for license in lf.getFreeLicenses():
            print license.encode('utf-8')

if __name__ == '__main__':
    main()