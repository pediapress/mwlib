#! /usr/bin/env python

# Copyright (c) 2007-2023 PediaPress GmbH
# See README.md for additional licensing information.

import glob
import os
import sys

from setuptools import setup, Extension


def get_version():
    d = {}
    exec(
        compile(open("src/mwlib/_version.py", "rb").read(), "mwlib/_version.py", "exec"),
        d,
        d,
    )
    return str(d["version"])


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


def main():
    if os.path.exists("Makefile"):
        build_deps()  # this is a git clone

    install_requires = ["Pillow", "setuptools"]

    ext_modules = []
    ext_modules.append(Extension("mwlib._uscan", sources=["src/mwlib/_uscan.cc"]))

    for x in glob.glob("mwlib/*/*.c"):
        modname = x[:-2].replace("/", ".")
        ext_modules.append(Extension(modname, [x]))

    console_scripts = [
        # "nslave = mwlib.main_trampoline:nslave_main",
        # "postman = mwlib.main_trampoline:postman_main",
        # "nserve = mwlib.main_trampoline:nserve_main",
        "mw-zip = mwlib.apps.buildzip:main",
        "mw-version = mwlib._version:main",
        "mw-render = mwlib.apps.render:main",
        # "mw-qserve = qs.qserve:main",
        # "mw-serve-ctl = mwlib.apps.serve:serve_ctl",
    ]

    setup(
        name="mwlib",
        version=get_version(),
        entry_points={
            "mwlib.writers": ["odf = mwlib.odfwriter:writer"],
            "console_scripts": console_scripts,
        },
        install_requires=install_requires,
        ext_modules=ext_modules,
        package_dir={"": "src"},
        packages=["mwlib", "mwlib.templ"],
        namespace_packages=["mwlib"],
        include_package_data=True,
        zip_safe=False,
        url="http://code.pediapress.com/",
        description="mediawiki parser and utility library",
        license="BSD Licenprse",
        maintainer="pediapress.com",
        maintainer_email="info@pediapress.com",
        long_description=open("README.md").read(),
    )


if __name__ == "__main__":
    main()
