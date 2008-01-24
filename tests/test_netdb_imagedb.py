#! /usr/bin/env py.test

import os
import shutil
import tempfile
import time

from mwlib.netdb import ImageDB

class TestImageDB(object):
    baseurls = (
        u'http://gibtsjagarnich.xyz/test/bla/', # no connect
        u'http://upload.wikimedia.org/wikipedia/de/', # 404
        u'http://upload.wikimedia.org/wikipedia/commons/', # 200
    )
    
    existing_image_name = u'Serra_de_Cals.jpg'
    existing_image_url = 'http://upload.wikimedia.org/wikipedia/commons/6/6b/Serra_de_Cals.jpg'
    nonexisting_image_name = u'Test12123213.jpg'
    
    def setup_class(cls):
        cls.tempdir = tempfile.mkdtemp()
    
    def teardown_class(cls):
        shutil.rmtree(cls.tempdir)
    
    def check(self, cachedir, size, grayscale, success):
        if success:
            name = self.existing_image_name
            check_url = self.existing_image_url
        else:
            name = self.nonexisting_image_name
            check_url = None
        
        time.sleep(0.5)
        imagedb = ImageDB(self.baseurls, cachedir)
        p = imagedb.getDiskPath(name, size=size, grayscale=grayscale)
        relpath = imagedb.getPath(name, size=size, grayscale=grayscale)
        assert imagedb.getURL(name) == check_url
        if success:
            assert os.path.exists(p)
            assert p.endswith(relpath)
            assert p != relpath
            assert relpath[0] != '/'
            imagedb.clear()
            if cachedir:
                assert p.startswith(cachedir)
            else:
                assert p.startswith(imagedb.cachedir)
                assert not os.path.exists(p)
        else:
            assert p is None
            imagedb.clear()
            if cachedir:
                assert os.path.exists(cachedir)
            else:
                assert not os.path.exists(imagedb.cachedir)
    
    def test_succeed_gen(self):
        for cachedir in (None, self.tempdir):
            for size in (None, 100):
                for grayscale in (False, True):
                    yield self.check, cachedir, size, grayscale, True
    
    def test_fail_get(self):
        for cachedir in (None, self.tempdir):
            for size in (None, 100):
                for grayscale in (False, True):
                    yield self.check, cachedir, size, grayscale, False
    
        
    
    
        