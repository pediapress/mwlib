#! /usr/bin/env py.test

import os
import tempfile
import glob


def pytest_generate_tests(metafunc):
    zipfiles = glob.glob(os.path.abspath(os.path.join(os.path.dirname(__file__),  "*.zip")))
    for name in writer_names():
        for z in zipfiles:
            metafunc.addcall(id="%s:%s" % (name, os.path.basename(z)), funcargs=dict(writer=name, input=z))


def writer_names():
    import pkg_resources
    retval = []
    for x in pkg_resources.iter_entry_points("mwlib.writers"):
        try:
            x.load()
        except Exception:
            pass
        else:
            retval.append(x.name)

    return retval


def test_render(writer, input):
    tmp = tempfile.mktemp()
    cmd = "mw-render -w %s -c %s -o %s" % (writer, input, tmp)
    print "running", cmd
    try:
        err = os.system(cmd)
        assert err == 0
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
