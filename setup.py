#! /usr/bin/env python

import os
import ez_setup
ez_setup.use_setuptools()
from setuptools import setup

install_requires=["simplejson>=1.7"]

def read_long_description():
    fn = os.path.join(os.path.dirname(os.path.abspath(__file__)), "README.txt")
    return open(fn).read()

setup(
    name="mwlib",
    version="0.0.2",
    entry_points = dict(console_scripts=['mw-buildcdb = mwlib.apps:buildcdb',
                                         'mw-zip = mwlib.apps:buildzip',
                                         'mw-parse = mwlib.apps:parse',
                                         'mw-show = mwlib.apps:show',
                                         'mw-html = mwlib.apps:html',
                                         ]),
    install_requires=install_requires,

    packages=["mwlib", "mwlib.Plex"],
    zip_safe = False,
    url = "http://code.pediapress.com/",
    description="mediawiki parser and utility library",
    long_description = read_long_description()
)

