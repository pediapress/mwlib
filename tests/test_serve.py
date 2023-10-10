#! /usr/bin/env py.test

import time

from mwlib.core import serve
from mwlib.utilities import myjson as json


def make_collection_dir(tmpdir, name):
    cid = serve.make_collection_id({"metabook": json.dumps({"title": name, "type": "collection"})})
    d = tmpdir.join(cid[0], cid[:2], cid).ensure(dir=1)
    d.join("output.rl").write("bla")
    return d


def test_purge_cache(tmpdir):
    d1 = make_collection_dir(tmpdir, "c1")
    d2 = make_collection_dir(tmpdir, "c2")
    d2.join("output.rl").setmtime(time.time() - 2)
    serve.purge_cache(1, tmpdir.strpath)
    assert d1.check()
    assert not d2.check()
