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
    
    def test_getAuthors(self):
        authors = self.w.getAuthors(u'Physics')
        print 'AUTHORS:', authors
        authors = self.w.getAuthors(u'Physics', revision='206917093')
        print 'AUTHORS:', authors
        
        w = WikiDB('http://en.wikipedia.com/w/') # note: the .com is on purpose!
        authors = w.getAuthors(u'Physics')
        print 'AUTHORS:', authors

    
    def test_parse_article_url(self):
        from mwlib.mwapidb import parse_article_url
        
        def p(url):
            d = parse_article_url(url)
            return d['api_helper'].base_url, d['title'], d['revision']
        
        b, t, r = p('http://de.wikipedia.org/wiki/Hauptseite')
        assert b == 'http://de.wikipedia.org/w/'
        assert t == u'Hauptseite'
        assert r is None

        b, t, r = p('http://de.wikipedia.org/wiki/August_Ferdinand_Möbius')
        assert b == 'http://de.wikipedia.org/w/'
        assert t == u'August Ferdinand Möbius'
        assert r is None
    
        b, t, r = p('http://de.wikipedia.org/w/index.php?title=August_Ferdinand_Möbius&oldid=38212551')
        assert b == 'http://de.wikipedia.org/w/'
        assert t == u'August Ferdinand Möbius'
        assert r == 38212551
    
        b, t, r = p('http://de.wikipedia.org/w/index.php?title=August_Ferdinand_Möbius&oldid=38212551')
        assert b == 'http://de.wikipedia.org/w/'
        assert t == u'August Ferdinand Möbius'
        assert r == 38212551

        b, t, r = p('http://wikieducator.org/Otago_Polytechnic')
        assert b == 'http://wikieducator.org/'
        assert t == u'Otago Polytechnic'
        assert r is None
        
        assert parse_article_url('bla') is None
        assert parse_article_url('http://pediapress.com/') is None
        
    def test_redirect(self):
        raw = self.w.getRawArticle(u'The European Library')
        assert 'redirect' not in raw.lower()

class TestImageDB(object):
    base_url = 'http://en.wikipedia.org/w/'
    
    existing_image_name = u'Serra de Cals.jpg'
    existing_image_url = 'http://upload.wikimedia.org/wikipedia/commons/6/6b/Serra_de_Cals.jpg'
    nonexisting_image_name = u'Test12123213.jpg'
    
    def setup_method(self, method):
        self.imagedb = ImageDB(self.base_url)
    
    def teardown_method(self, method):
        self.imagedb.clear()
    
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
        p = self.imagedb.getDiskPath(name, size=size)
        assert self.imagedb.getURL(name, size=size) == check_url
        if success:
            assert os.path.exists(p)
        else:
            assert p is None
    
    def test_succeed_gen(self):
        for size in (None, 100):
            yield self.check, size, True
    
    def test_fail_get(self):
        for size in (None, 100):
            yield self.check, size, False
    
    def test_spaces_in_imagename(self):
        name = u'DNA As Structure Formula (German).PNG'
        size = 100
        p = self.imagedb.getDiskPath(name, size=size)
        assert p is not None
    
    def test_unicode_imagename(self):
        name = u'Balneario_Iporá_lago_02.jpg'
        size = 100
        p = self.imagedb.getDiskPath(name, size=size)
        assert p is not None
    
    def test_resize(self):
        big_size = 2000
        
        p = self.imagedb.getDiskPath(self.existing_image_name)
        img = Image.open(p)
        orig_size = img.size
        print 'ORIG', orig_size
        assert orig_size[0] < big_size
        assert orig_size[1] < big_size
        
        p = self.imagedb.getDiskPath(self.existing_image_name, size=100)
        img = Image.open(p)
        print 'CONVERTED1', img.size
        assert img.size[0] == 100
        assert img.size[1] < 100
        
        p = self.imagedb.getDiskPath(self.existing_image_name, size=big_size)
        img = Image.open(p)
        print 'CONVERTED2', img.size
        assert img.size == orig_size
    
    def test_getLicense(self):
        license = self.imagedb.getLicense(self.existing_image_name)
        assert license == u'Cc-by-sa-1.0'
    
    def test_svg(self):
        url = self.imagedb.getURL(u'Flag of the United States.svg', size=800)
        assert not url.endswith('.svg')
    
    def test_non_full_url(self):
        """WikiEducator (any probably many other MediaWikis) return image URLs
        that do not start with http://hostname.
        """
        
        imgdb = ImageDB('http://wikieducator.org/')
        t = u'Mediawiki_logo_m.png'
        assert imgdb.getURL(t).startswith('http://')
        imgdb.getDiskPath(t)
    
    def test_getDescriptionURL(self):
        imgdb = ImageDB('http://en.wikipedia.org/w/')
        t = u'Sertraline-A-3D-balls.png'
        du = imgdb.getDescriptionURL(t)
        assert du == 'http://commons.wikimedia.org/wiki/Image:Sertraline-A-3D-balls.png'
