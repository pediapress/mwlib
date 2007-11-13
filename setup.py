#! /usr/bin/env python

# Copyright (c) 2007, PediaPress GmbH
# See README.txt for additional licensing information.

import sys
import os
import ez_setup
ez_setup.use_setuptools()
from setuptools import setup

install_requires=["simplejson>=1.3"]
if sys.version_info[:2] < (2,5):
    install_requires.append("wsgiref>=0.1.2")


def read_long_description():
    fn = os.path.join(os.path.dirname(os.path.abspath(__file__)), "README.txt")
    return open(fn).read()

setup(
    name="mwlib",
    version="0.1.0",
    entry_points = dict(console_scripts=['mw-buildcdb = mwlib.apps:buildcdb',
                                         'mw-zip = mwlib.apps:buildzip',
                                         'mw-parse = mwlib.apps:parse',
                                         'mw-show = mwlib.apps:show',
                                         'mw-html = mwlib.apps:html',
                                         'mw-serve = mwlib.apps:serve',
                                         ]),
    install_requires=install_requires,

    packages=["mwlib", "mwlib.Plex", "mwlib.resources"],
    include_package_data = True,
    zip_safe = False,
    url = "http://code.pediapress.com/",
    description="mediawiki parser and utility library",
    license="BSD License",
    maintainer="pediapress.com",
    maintainer_email="info@pediapress.com",
    long_description = read_long_description()
)
