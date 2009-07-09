#! /usr/bin/env py.test

import os
import tempfile

def pytest_generate_tests(metafunc):
    p = os.path.abspath(os.path.join(os.path.dirname(__file__),  "speisesalz.zip"))
    for name in writer_names():
        metafunc.addcall(id=name, funcargs=dict(writer=name, input=p))
        
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
        err=os.system(cmd)
        assert err==0
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
