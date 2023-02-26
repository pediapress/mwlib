#! /usr/bin/env py.test

import glob
import os

import pytest


def zip_files():
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


@pytest.fixture(params=zip_files())
def zip_file(request):
    return request.param


@pytest.fixture(autouse=True)
def skip_by_invalid_writer_zipfile_combination(request, writer, zip_file):
    if request.node.get_closest_marker("skip_writer_zipfile"):
        marker = request.node.get_closest_marker("skip_writer_zipfile")
        if marker and marker.args and marker.args[0] == writer and marker.args[1] in zip_file:
            pytest.skip("skipping because of bug in %s writer" % writer)


@pytest.mark.skip_writer_zipfile("rl", "lambda.zip")
def test_render(writer, zip_file, tmpdir):
    cmd = "mw-render -w %s -c %s -o %s" % (writer, zip_file, tmpdir.join("output"))
    print(("running", cmd))
    err = os.system(cmd)
    assert err == 0
