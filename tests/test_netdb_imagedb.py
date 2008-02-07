#! /usr/bin/env py.test
# -*- coding: utf-8 -*-

import os
import shutil
import tempfile
import time

from PIL import Image

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
        assert imagedb.getURL(name, size=size, grayscale=grayscale) == check_url
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
    
    def test_spaces_in_imagename(self):
        imagedb = ImageDB(self.baseurls, self.tempdir)
        name = u'DNA As Structure Formula (German).PNG'
        size = 100
        grayscale = True
        p = imagedb.getDiskPath(name, size=size, grayscale=grayscale)
        assert p is not None
    
    def test_unicode_imagename(self):
        imagedb = ImageDB(self.baseurls, self.tempdir)
        name = u'Balneario_Iporá_lago_02.jpg'
        size = 100
        grayscale = True
        p = imagedb.getDiskPath(name, size=size, grayscale=grayscale)
        assert p is not None
    
    def test_resize(self):
        big_size = 2000
        
        imagedb = ImageDB(self.baseurls, self.tempdir)
        p = imagedb.getDiskPath(self.existing_image_name)
        img = Image.open(p)
        orig_size = img.size
        print 'ORIG', orig_size
        assert orig_size[0] < big_size
        assert orig_size[1] < big_size

        p = imagedb.getDiskPath(self.existing_image_name, size=100)
        img = Image.open(p)
        print 'CONVERTED1', img.size
        assert img.size[0] == 100
        assert img.size[1] < 100
        
        p = imagedb.getDiskPath(self.existing_image_name, size=big_size)
        img = Image.open(p)
        print 'CONVERTED2', img.size
        assert img.size == orig_size
    

        
        