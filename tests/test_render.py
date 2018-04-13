#! /usr/bin/env py.test

import os
import glob
import pytest


def zipfiles():
    return glob.glob(os.path.abspath(os.path.join(os.path.dirname(__file__), "*.zip")))


def writer_names():
    import pkg_resources
    for x in pkg_resources.iter_entry_points("mwlib.writers"):
        try:
            x.load()
            yield x.name
        except Exception:
            pass


@pytest.fixture(params=writer_names())
def writer(request):
    return request.param


@pytest.fixture(params=zipfiles())
def zipfile(request):
    return request.param


def test_render(writer, zipfile, tmpdir):
    cmd = "mw-render -w %s -c %s -o %s" % (writer, zipfile, tmpdir.join("output"))
    print "running", cmd
    err = os.system(cmd)
    assert err == 0
