#! /usr/bin/env python

# Copyright (c) 2007, PediaPress GmbH
# See README.txt for additional licensing information.

import sys
import os

try:
    from setuptools import setup
    # got the following error while setuptools installed simplejson,
    # when trying import ez_setup first:
    # TypeError: use_setuptools() got an unexpected keyword argument 'min_version'
    # so, only import it if setuptools is not already installed
except ImportError:
    import ez_setup
    ez_setup.use_setuptools(version="0.6c1")

from setuptools import setup
import distutils.util


install_requires=["simplejson>=1.3"]
if sys.version_info[:2] < (2,5):
    install_requires.append("wsgiref>=0.1.2")

execfile(distutils.util.convert_path('mwlib/_version.py')) 
# adds 'version' to local namespace

def read_long_description():
    fn = os.path.join(os.path.dirname(os.path.abspath(__file__)), "README.txt")
    return open(fn).read()

setup(
    name="mwlib",
    version=str(version),
    entry_points = dict(console_scripts=['mw-buildcdb = mwlib.apps:buildcdb',
                                         'mw-zip = mwlib.apps:buildzip',
                                         'mw-parse = mwlib.apps:parse',
                                         'mw-show = mwlib.apps:show',
                                         'mw-html = mwlib.apps:html',
                                         'mw-serve = mwlib.apps:serve',
                                         ]),
    install_requires=install_requires,
    
    packages=["mwlib", "mwlib.Plex", "mwlib.resources"],
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
