#! /usr/bin/env py.test

from mwlib import myjson as json
import os
import shutil
import tempfile
import time

from mwlib import serve


class TestServe(object):
    def setup_class(cls):
        cls.tmpdir = tempfile.mkdtemp()

    def teardown_class(cls):
        shutil.rmtree(cls.tmpdir)

    def mkcolldir(self, name):
        cid = serve.make_collection_id({'metabook': json.dumps({'title': name,  "type":"collection"})})
        d = os.path.join(self.tmpdir, cid[0], cid[:2], cid)
        os.makedirs(d)
        f = open(os.path.join(d, 'output.rl'), 'wb')
        f.write('bla')
        f.close()
        return d

    def test_purge_cache(self):
        d1 = self.mkcolldir('c1')
        d2 = self.mkcolldir('c2')
        time.sleep(2)
        os.utime(os.path.join(d1, 'output.rl'), None)
        serve.purge_cache(1, self.tmpdir)
        assert os.path.exists(d1)
        assert not os.path.exists(d2)
