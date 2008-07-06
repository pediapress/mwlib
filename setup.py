#! /usr/bin/env python

# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.

import sys
import os

import ez_setup
ez_setup.use_setuptools()

from setuptools import setup, Extension
import distutils.util


install_requires=["simplejson>=1.3", "pyparsing>=1.4.11", "odfpy>=0.7.0", "flup>=1.0"]
if sys.version_info[:2] < (2,5):
    install_requires.append("wsgiref>=0.1.2")
    install_requires.append("elementtree>=1.2.6")
    
execfile(distutils.util.convert_path('mwlib/_version.py')) 
# adds 'version' to local namespace

# we will *not* add support for automatic generation of those files as that
# might break with source distributions from pypi

if not os.path.exists(distutils.util.convert_path('mwlib/_mwscan.cc')):
    print "Error: please install re2c from http://re2c.org/ and run make"
    sys.exit(10)

def mtime(fn):
    return os.stat(distutils.util.convert_path(fn)).st_mtime

if mtime("mwlib/_mwscan.cc") < mtime("mwlib/_mwscan.re"):
    print "Warning: _mwscan.cc is older than _mwscan.re. please run make.\n"
    import time
    time.sleep(2)
    
    
def read_long_description():
    fn = os.path.join(os.path.dirname(os.path.abspath(__file__)), "README.txt")
    return open(fn).read()

setup(
    name="mwlib",
    version=str(version),
    entry_points = {'console_scripts': ['mw-buildcdb = mwlib.apps:buildcdb',
                                        'mw-zip = mwlib.apps:buildzip',
                                        'mw-post = mwlib.apps:post',
                                        'mw-render = mwlib.apps:render',
                                        'mw-parse = mwlib.apps:parse',
                                        'mw-show = mwlib.apps:show',
                                        'mw-html = mwlib.apps:html',
                                        'mw-serve = mwlib.apps:serve',
                                        'mw-watch = mwlib.apps:watch',
                                        'mw-testserve = mwlib.apps:testserve',
                                        ],
                    'mwlib.writers': ['odf = mwlib.odfwriter:writer',
                                      'xhtml = mwlib.xhtmlwriter:xhtmlwriter',
                                      'mwxml = mwlib.xhtmlwriter:xmlwriter',
                                      'docbook = mwlib.docbookwriter:writer',
                                      ]},
    install_requires=install_requires,
    ext_modules = [Extension("mwlib._mwscan", ["mwlib/_mwscan.cc"]),
                   #Extension("mwlib._expander", ["mwlib/_expander.cc"]),
                   ],
    
    packages=["mwlib", "mwlib.resources"],
    namespace_packages=['mwlib'],
    include_package_data = True,
    zip_safe = False,
    url = "http://code.pediapress.com/",
    description="mediawiki parser and utility library",
    license="BSD License",
    maintainer="pediapress.com",
    maintainer_email="info@pediapress.com",
    long_description = read_long_description()
)
