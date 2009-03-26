#! /usr/bin/env python
#! -*- coding:utf-8 -*-

# Copyright (c) 2007, PediaPress GmbH
# See README.txt for additional licensing information.

from __future__ import division

import os
import csv
import sys
import tempfile
try:
    import json
except ImportError:
    import simplejson as json


class License(object):

    def __init__(self, name='', display_name='', license_type=None):
        self.name = name
        self.display_name = display_name
        self.license_type = license_type # free|nonfree|unrelated|unknown
        

    def __str__(self):
        if self.display_name:
            display_name = ' - text: %s' % self.display_name
        else:
            display_name = ''
        return "<License:%(name)r - type:%(type)r%(displayname)r>" % { 'name': self.name,
                                                                       'type': self.license_type,
                                                                       'displayname': display_name,
                                                                       }
        
        
class LicenseChecker(object):

    def __init__(self, image_db=None, filter_type=None):
        self.image_db = image_db
        self.filter_type = self._checkFilterType(filter_type, default_filter='blacklist')
        self.licenses = {}
        self.initStats()
        
    def readLicensesCSV(self, fn=None):
        if not fn:
            fn = os.path.join(os.path.dirname(__file__), 'wplicenses.csv')
        for (name, display_name, license_type, dummy, license_description) in csv.reader(open(fn)):
            if not name:
                continue            
            name = unicode(name, 'utf-8').lower()
            lic = License(name=name)
            lic.display_name = unicode(display_name, 'utf-8')
            self.licenses[name] = lic.name
            if license_type in ['free-display', 'nonfree-display']:
                lic.license_type = 'free'
            elif license_type in ['nonfree']:
                lic.license_type = 'nonfree'                
            else:
                lic.license_type = 'unrelated'
            self.licenses[name] = lic

    def initStats(self):
        self.unknown_licenses = {}
        self.rejected_images = set()
        self.accepted_images = set()
        self.license_display_name = {}
        
        
    def _checkFilterType(self, filter_type=None, default_filter='blacklist'):
        if filter_type in ['blacklist', 'whitelist']:
            return filter_type
        else:
            return default_filter


    def _getLicenses(self, templates, imgname):
        licenses = []
        for template in templates:
            assert isinstance(template, unicode)
            lic = self.licenses.get(template, None)
            if not lic:
                lic = License(name=template)
                lic.license_type = 'unknown'
            licenses.append(lic)
        return licenses       


    def _checkLicenses(self, licenses, imgname):
        assert self.image_db, 'No image_db passed when initializing LicenseChecker'
        for lic in licenses:            
            if lic.license_type == 'free':
                self.license_display_name[imgname] = lic.display_name
                return True
            elif lic.license_type == 'nonfree':
                self.license_display_name[imgname] = lic.display_name
                return False
        for lic in licenses:
            if lic.license_type == 'unknown':
                urls = self.unknown_licenses.get(lic.name, set())
                urls.add(self.image_db.getDescriptionURL(imgname) or self.image_db.getURL(imgname) or imgname)
                self.unknown_licenses[lic.name] = urls
            
        self.license_display_name[imgname] = ''
        if self.filter_type == 'whitelist':
            return False
        elif self.filter_type == 'blacklist':
            return True


    def displayImage(self, imgname):
        assert self.image_db, 'No image_db passed when initializing LicenseChecker'
        templates = [t.lower() for t in self.image_db.getImageTemplates(imgname)]
        licenses = self._getLicenses(templates, imgname)
        display_img = self._checkLicenses(licenses, imgname)
        url = self.image_db.getDescriptionURL(imgname) or self.image_db.getURL(imgname) or imgname
        if display_img:
            self.accepted_images.add(url)
        else:
            self.rejected_images.add(url)
        return display_img


    def getLicenseDisplayName(self, imgname):
        text = self.license_display_name.get(imgname, None)        
        if not text == None:
            return text
        else:
            self.displayImage(imgname)
            return self.license_display_name.get(imgname, '')

    @property
    def free_img_ratio(self):
        r = len(self.rejected_images)
        a = len(self.accepted_images)
        if a + r > 0:
            ratio = a/(a+r)
        else:
            ratio = 1
        return ratio
        
    def dumpStats(self):
        stats = []
        stats.append('IMAGE LICENSE STATS - accepted: %d - rejected: %d --> accept ratio: %.2f' % (len(self.accepted_images), len(self.rejected_images), self.free_img_ratio))

        images = set()
        for urls in self.unknown_licenses.values():
            for url in urls:
                images.add(repr(url))        
        stats.append('Images without license information: %s' % (' '.join(list(images))))
        stats.append('##############################')
        stats.append('Rejected Images: %s' % ' '.join(list(self.rejected_images)))
        return '\n'.join(stats)

    def dumpUnknownLicenses(self, _dir):
        if not self.unknown_licenses:
            return
        fn = tempfile.mktemp(dir=_dir, prefix='licensestats_',  suffix='.json')
        f = open(fn, 'w')
        unknown_licenses = {}
        for (license, urls) in self.unknown_licenses.items():
            unknown_licenses[license] = list(urls)
        f.write(json.dumps(unknown_licenses))
        f.close()


    def analyseUnknownLicenses(self, _dir):
        files = os.listdir(_dir)
        unknown_licenses = {}
        for fn in files:
            fn = os.path.join(_dir, fn)
            if not fn.endswith('json'):
                continue
            content = unicode(open(fn).read(), 'utf-8')
            try:
                licenses = json.loads(content)
            except ValueError:
                print 'no json object found in file', fn
                continue
            for (license, urls) in licenses.items():
                if self.licenses.get(license, False) == False:
                    seen_urls = unknown_licenses.get(license, set())
                    seen_urls.update(set(urls))
                    unknown_licenses[license] = seen_urls
        sorted_licenses = [ (len(urls), license, urls) for license, urls in unknown_licenses.items()]
        sorted_licenses.sort(reverse=True)
        for num_urls, license, urls in sorted_licenses:
            print "\nTEMPLATE: %(template)s (num rejected images: %(num_images)d)\nIMAGES:\n%(img_str)s\n" % { 'template': repr(license),
                                                                                                               'num_images': num_urls,
                                                                                                               'img_str': '\n'.join([repr(i) for i in list(urls)[:5]])
                }

                    
if __name__ == '__main__':

    lc = LicenseChecker()
    lc.readFreeLicensesCSV()

    if len(sys.argv) > 1:
        stats_dir = sys.argv[1]
    else:
        stats_dir = os.environ.get('HIQ_STATSDIR')
    if not stats_dir:
        print 'specify stats_dir as first arg, or set environment var HIQ_STATSIDR'
        sys.exit(1)

    
    lc.analyseUnknownLicenses(stats_dir)
