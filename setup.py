#! /usr/bin/env python

# Copyright (c) 2007-2011 PediaPress GmbH
# See README.rst for additional licensing information.

import sys, os, time, glob

if not (2, 4) < sys.version_info[:2] < (3, 0):
    sys.exit("""
***** ERROR ***********************************************************
* mwlib does not work with python %s.%s. You need to use python 2.5,
* 2.6 or 2.7
***********************************************************************
""" % sys.version_info[:2])


from setuptools import setup, Extension
from distutils.command.build import build
from distutils.util import strtobool
PP_MAINTAINER = strtobool(os.environ.get("PP_MAINTAINER", "0"))


def get_version():
    d = {}
    execfile("mwlib/_version.py", d, d)
    return str(d["version"])


class MakeBuild(build):
    def run(self):
        self.run_make()
        build.run(self)

    def run_make(self):
        if not os.path.exists('Makefile'):
            return
        
        # we will *not* add support for automatic generation of those files as that
        # might break with source distributions from pypi
        err = os.system("make all")
        if err != 0:
            sys.exit("Error: make failed")
        

def main():
    install_requires = ["pyparsing>=1.4.11", "timelib>=0.2",
                        "bottle>=0.10", "pyPdf>=1.12", "apipkg>=1.2",
                        "qserve>=0.2.7", "lxml", "py>=1.4",
                        "sqlite3dbm", "simplejson>=2.3", "cython"]

    if not PP_MAINTAINER:
        install_requires += ["roman", "gevent", "PIL", "odfpy>=0.9, <0.10"]

    ext_modules = []
    ext_modules.append(Extension("mwlib._uscan", ["mwlib/_uscan.cc"]))

    for x in glob.glob("mwlib/*/*.c"):
        modname = x[:-2].replace("/", ".")
        ext_modules.append(Extension(modname, [x]))

    setup(
        name="mwlib",
        version=get_version(),
        cmd_class={'build': MakeBuild},
        entry_points={'mwlib.writers': ['odf = mwlib.odfwriter:writer']},
        install_requires=install_requires,
        ext_modules=ext_modules,
        packages=["mwlib", "mwlib.templ"],
        namespace_packages=['mwlib'],
        scripts=("sandbox/nslave.py", "sandbox/nserve.py", "sandbox/postman.py",
                 "mw-zip", "mw-version", "mw-render", "mw-qserve", "mw-serve-ctl"),
        include_package_data=True,
        zip_safe=False,
        url="http://code.pediapress.com/",
        description="mediawiki parser and utility library",
        license="BSD License",
        maintainer="pediapress.com",
        maintainer_email="info@pediapress.com",
        long_description=open("README.rst").read())


if __name__ == '__main__':
    main()
