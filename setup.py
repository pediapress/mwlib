#! /usr/bin/env python

# Copyright (c) 2007-2009 PediaPress GmbH
# See README.txt for additional licensing information.

import sys
import os
import time
import ez_setup
ez_setup.use_setuptools()

from setuptools import setup, Extension
import distutils.util

execfile(distutils.util.convert_path('mwlib/_version.py')) 
# adds 'version' to local namespace

def checkpil():
    try:
        from PIL import Image
        return
    except ImportError:
        pass
    
    print """

    *****************************************************
    * please install the python imaging library (PIL)
    * from http://www.pythonware.com/products/pil/
    *****************************************************

    """
    # give them some time to read it, we really need it and can't install with setuptools
    time.sleep(5) 

def mtime(fn):
    fn = distutils.util.convert_path(fn)
    if os.path.exists(fn):
        return os.stat(distutils.util.convert_path(fn)).st_mtime
    return 0

def build_deps():
    # we will *not* add support for automatic generation of those files as that
    # might break with source distributions from pypi
            
    if mtime("mwlib/_uscan.cc") < mtime("mwlib/_uscan.re"):
        err=os.system("re2c --version")
        if err not in (0, 512) and sys.platform!="win32":
            sys.exit("Error: please install re2c from http://re2c.org")
        
        cmd = "re2c -w --no-generation-date -o %s %s" % (distutils.util.convert_path('mwlib/_uscan.cc'),
                                                         distutils.util.convert_path('mwlib/_uscan.re'))
        print "Running", cmd
        err = os.system(cmd)
        
        if err!=0:
            sys.exit("Error: re2c failed.")
            
def read_long_description():
    fn = os.path.join(os.path.dirname(os.path.abspath(__file__)), "README.txt")
    return open(fn).read()

def main():
    if os.path.exists(distutils.util.convert_path('Makefile')):
        build_deps()   # this is a hg checkout.

    install_requires=["pyparsing>=1.4.11", "odfpy>=0.9, <0.10", "flup>=1.0", "twisted>=8.2", "lockfile==0.8", "timelib>=0.2", "WebOb>=0.9", "pyPdf>=1.12", "apipkg", "qserve", "roman"]
    if sys.version_info[:2] < (2,5):
        install_requires.append("wsgiref>=0.1.2")
        install_requires.append("elementtree>=1.2.6")
    if sys.version_info[:2] < (2,6):
        install_requires.append("simplejson>=1.3")

    ext_modules = []
    ext_modules.append(Extension("mwlib._uscan", ["mwlib/_uscan.cc"]))

    import glob
    for x in glob.glob("mwlib/*/*.c"):
        modname = x[:-2].replace("/", ".")
        ext_modules.append(Extension(modname, [x]))
        print "USING:", modname, x
        
        
    setup(
        name="mwlib",
        version=str(version),
        dependency_links = ["http://code.pediapress.com/dl/"],
        entry_points = {'console_scripts': ['mw-buildcdb = mwlib.apps:buildcdb',
                                            'mw-zip = mwlib.apps.buildzip:main',
                                            'mw-post = mwlib.apps:post',
                                            'mw-render = mwlib.apps.render:main',
                                            'mw-parse = mwlib.apps:parse',
                                            'mw-show = mwlib.apps:show',
                                            'mw-serve = mwlib.apps.serve:main',
                                            'mw-serve-ctl = mwlib.apps.serve:serve_ctl',
                                            'mw-check-service = mwlib.apps.serve:check_service',
                                            'mw-watch = mwlib.apps.watch:main',
                                            'mw-client = mwlib.apps.client:main',
                                            'mw-version = mwlib._version:main',
                                            'mw-qserve = qs.qserve:main',
                                            ],
                        'mwlib.writers': ['odf = mwlib.odfwriter:writer',
                                          'xhtml = mwlib.xhtmlwriter:xhtmlwriter',
                                          'docbook = mwlib.docbookwriter:writer',
                                          ]},
        install_requires=install_requires,
        ext_modules=ext_modules,
        packages=["mwlib", "mwlib.templ"],
        namespace_packages=['mwlib'],
        py_modules=["argv"],
        scripts = "sandbox/nslave.py sandbox/nserve.py sandbox/postman.py".split(),
        include_package_data = True,
        zip_safe = False,
        url = "http://code.pediapress.com/",
        description="mediawiki parser and utility library",
        license="BSD License",
        maintainer="pediapress.com",
        maintainer_email="info@pediapress.com",
        long_description = read_long_description()
    )
    checkpil()
    
if __name__=='__main__':
    main()
