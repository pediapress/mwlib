#! /usr/bin/env python

# Copyright (c) 2007-2011 PediaPress GmbH
# See README.rst for additional licensing information.

import sys, os, time, glob

if not (2, 4) < sys.version_info[:2] < (3, 0):
    sys.exit("""
***** ERROR ***********************************************************
* mwlib does not work with your python version. You need to use python
* 2.5, 2.6 or 2.7
***********************************************************************
""")

try:
    from setuptools import setup, Extension
except ImportError:
    import ez_setup
    ez_setup.use_setuptools()
    from setuptools import setup, Extension


def get_version():
    d = {}
    execfile("mwlib/_version.py", d, d)
    return str(d["version"])


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
    if os.path.exists(fn):
        return os.stat(fn).st_mtime
    return 0


def build_deps():
    # we will *not* add support for automatic generation of those files as that
    # might break with source distributions from pypi
    err = os.system("make all")
    if err != 0:
        sys.exit("Error: make failed")


def read_long_description():
    return open("README.rst").read()


def main():
    if os.path.exists('Makefile'):
        build_deps()   # this is a git clone

    install_requires = ["pyparsing>=1.4.11", "odfpy>=0.9, <0.10",
                        "gevent", "timelib>=0.2", "bottle>=0.10",
                        "pyPdf>=1.12", "apipkg", "qserve>=0.2.3",
                        "roman", "lxml", "py>=1.4", "sqlite3dbm"]
    if sys.version_info[:2] < (2, 6):
        install_requires.append("simplejson>=1.3")

    ext_modules = []
    ext_modules.append(Extension("mwlib._uscan", ["mwlib/_uscan.cc"]))

    for x in glob.glob("mwlib/*/*.c"):
        modname = x[:-2].replace("/", ".")
        ext_modules.append(Extension(modname, [x]))
        print "USING:", modname, x

    setup(
        name="mwlib",
        version=get_version(),
        entry_points={'console_scripts': ['mw-buildcdb = mwlib.apps:buildcdb',
                                          'mw-zip = mwlib.apps.buildzip:main',
                                          'mw-post = mwlib.apps:post',
                                          'mw-render = mwlib.apps.render:main',
                                          'mw-parse = mwlib.apps:parse',
                                          'mw-show = mwlib.apps:show',
                                          'mw-serve-ctl = mwlib.apps.serve:serve_ctl',
                                          'mw-check-service = mwlib.apps.serve:check_service',
                                          'mw-watch = mwlib.apps.watch:main',
                                          'mw-client = mwlib.apps.client:main',
                                          'mw-version = mwlib._version:main',
                                          'mw-qserve = qs.qserve:main'],
                      'mwlib.writers': ['odf = mwlib.odfwriter:writer']},
        install_requires=install_requires,
        ext_modules=ext_modules,
        packages=["mwlib", "mwlib.templ"],
        namespace_packages=['mwlib'],
        py_modules=["argv"],
        scripts="sandbox/nslave.py sandbox/nserve.py sandbox/postman.py".split(),
        include_package_data=True,
        zip_safe=False,
        url="http://code.pediapress.com/",
        description="mediawiki parser and utility library",
        license="BSD License",
        maintainer="pediapress.com",
        maintainer_email="info@pediapress.com",
        long_description=read_long_description())

    if "install" in sys.argv or "develop" in sys.argv:
        checkpil()

if __name__ == '__main__':
    main()
