#! /usr/bin/env py.test
# -*- coding: utf-8 -*-

import os
import shutil
import tempfile
import time

from PIL import Image

from mwlib.mwapidb import ImageDB, WikiDB

class TestWikiDB(object):
    base_url = 'http://en.wikipedia.org/w/'
    
    def setup_method(self, method):
        self.w = WikiDB(self.base_url)
    
    def test_getRawArticle(self):
        raw = self.w.getRawArticle(u'Mathematics')
        assert isinstance(raw, unicode)
        assert len(raw) > 100
        
        raw2 = self.w.getRawArticle(u'Mathematics', revision='205593066')
        assert isinstance(raw2, unicode)
        assert len(raw2) > 100
        assert raw2 != raw
        
        assert None is self.w.getRawArticle('gibsjagarnich')
        assert None is self.w.getRawArticle(u'Mathematics', revision='1223423')
    
    def test_getURL(self):
        assert self.w.getURL(u'Mathematics') == '%sindex.php?title=Mathematics' % self.base_url
    
    def test_getTemplate(self):
        raw = self.w.getTemplate('Infobox')
        assert isinstance(raw, unicode)
        assert len(raw) > 10
        

class TestImageDB(object):
    base_url = 'http://en.wikipedia.org/w/'
    
    existing_image_name = u'Serra_de_Cals.jpg'
    existing_image_url = 'http://upload.wikimedia.org/wikipedia/commons/6/6b/Serra_de_Cals.jpg'
    nonexisting_image_name = u'Test12123213.jpg'
    
    def setup_class(cls):
        cls.tempdir = tempfile.mkdtemp()
    
    def teardown_class(cls):
        shutil.rmtree(cls.tempdir)
    
    def check(self, size, success):
        if success:
            name = self.existing_image_name
            if size is None:
                check_url = self.existing_image_url
            else:
                check_url = 'http://upload.wikimedia.org/wikipedia/commons/thumb/6/6b/Serra_de_Cals.jpg/%spx-Serra_de_Cals.jpg' % size
        else:
            name = self.nonexisting_image_name
            check_url = None
        
        time.sleep(0.5)
        imagedb = ImageDB(self.base_url)
        p = imagedb.getDiskPath(name, size=size)
        assert imagedb.getURL(name, size=size) == check_url
        if success:
            assert os.path.exists(p)
            imagedb.clear()
        else:
            assert p is None
            imagedb.clear()
    
    def test_succeed_gen(self):
        for size in (None, 100):
            yield self.check, size, True
    
    def test_fail_get(self):
        for size in (None, 100):
            yield self.check, size, False
    
    def test_spaces_in_imagename(self):
        imagedb = ImageDB(self.base_url)
        name = u'DNA As Structure Formula (German).PNG'
        size = 100
        p = imagedb.getDiskPath(name, size=size)
        assert p is not None
    
    def test_unicode_imagename(self):
        imagedb = ImageDB(self.base_url)
        name = u'Balneario_Iporá_lago_02.jpg'
        size = 100
        p = imagedb.getDiskPath(name, size=size)
        assert p is not None
    
    def test_resize(self):
        big_size = 2000
        
        imagedb = ImageDB(self.base_url)
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
