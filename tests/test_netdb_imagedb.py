#! /usr/bin/env py.test
# -*- coding: utf-8 -*-

import os
import shutil
import tempfile
import time

from PIL import Image

from mwlib.netdb import ImageDB, NetDB

class TestImageDB(object):
    baseurls = (
        u'http://gibtsjagarnich.xyz/test/bla/', # no connect
        u'http://upload.wikimedia.org/wikipedia/de/', # 404
        u'http://upload.wikimedia.org/wikipedia/commons/', # 200
    )
    
    existing_image_name = u'Serra_de_Cals.jpg'
    existing_image_url = 'http://upload.wikimedia.org/wikipedia/commons/6/6b/Serra_de_Cals.jpg'
    nonexisting_image_name = u'Test12123213.jpg'
    
    # config for NetDB:
    articleurl = 'http://en.wikipedia.org/w/index.php?title=@TITLE@&action=raw'
    templateurls = [
        'http://en.wikipedia.org/w/index.php?title=Template:@TITLE@&action=raw',
    ]
    imagedescriptionurls = [
        'http://gibsjagarnicht.xyz/test/bla/@TITLE@',
        'http://de.wikipedia.org/w/index.php?title=Bild:@TITLE@&action=raw',
        'http://commons.wikipedia.org/w/index.php?title=Image:@TITLE@&action=raw',
    ]
    knownLicenses = [
        'GFDL', 'cc-by-sa',
    ]
    
    def setup_class(cls):
        cls.tempdir = tempfile.mkdtemp()
    
    def teardown_class(cls):
        shutil.rmtree(cls.tempdir)
    
    def check(self, cachedir, size, success):
        if success:
            name = self.existing_image_name
            check_url = self.existing_image_url
        else:
            name = self.nonexisting_image_name
            check_url = None
        
        time.sleep(0.5)
        imagedb = ImageDB(self.baseurls, cachedir)
        p = imagedb.getDiskPath(name, size=size)
        relpath = imagedb.getPath(name, size=size)
        assert imagedb.getURL(name, size=size) == check_url
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
                yield self.check, cachedir, size, True
    
    def test_fail_get(self):
        for cachedir in (None, self.tempdir):
            for size in (None, 100):
                yield self.check, cachedir, size, False
    
    def test_spaces_in_imagename(self):
        imagedb = ImageDB(self.baseurls, self.tempdir)
        name = u'DNA As Structure Formula (German).PNG'
        size = 100
        p = imagedb.getDiskPath(name, size=size)
        assert p is not None
    
    def test_unicode_imagename(self):
        imagedb = ImageDB(self.baseurls, self.tempdir)
        name = u'Balneario_Iporá_lago_02.jpg'
        size = 100
        p = imagedb.getDiskPath(name, size=size)
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
    
    def test_license(self):
        wikidb = NetDB(
            pagename=self.articleurl,
            templateurls=self.templateurls,
            imagedescriptionurls=self.imagedescriptionurls,
        )
        imagedb = ImageDB(self.baseurls, self.tempdir,
            wikidb=wikidb,
            knownLicenses=self.knownLicenses,
        )
        p = imagedb.getDiskPath(self.existing_image_name, size=100)
        templates = imagedb.getImageTemplates(self.existing_image_name)
        print 'TEMPLATES:', templates
    

    
