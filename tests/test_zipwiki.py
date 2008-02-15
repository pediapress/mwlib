#! /usr/bin/env py.test

import os
from zipfile import ZipFile

from mwlib import parser, zipwiki

zip_filename = os.path.join(os.path.dirname(__file__), 'data', 'test.zip')

class TestZipWiki(object):
    def setup_method(self, method):
        self.wikidb = zipwiki.Wiki(zip_filename)
        self.imagedb = zipwiki.ImageDB(zip_filename)
    
    def teardown_method(self, method):
        self.imagedb.clean()
    
    def test_getRawArticle(self):
        a = self.wikidb.getRawArticle(u'Lernspiel')
        assert isinstance(a, unicode)
        assert len(a) > 0
        a = self.wikidb.getRawArticle(u'Lernspiel', revision=123)
        assert a is None
    
    def test_getParsedArticle(self):
        p = self.wikidb.getParsedArticle(u'Daniel Caspary')
        assert isinstance(p, parser.Article)
    
    def test_getURL(self):
        url = self.wikidb.getURL(u'Mamo Wolde')
        assert url == 'http://mw/dewiki/index.php?title=Mamo_Wolde&oldid=0&action=raw'
    
    def test_getTemplate(self):
        t = self.wikidb.getTemplate(u'Navigationsleiste Olympiasieger im Marathon')
        assert isinstance(t, unicode)
        t = self.wikidb.getTemplate(u'no-such-template')
        assert t is None
    
    def test_ImageDB(self):
        p = self.imagedb.getDiskPath(u'Shut the box.jpg')
        assert isinstance(p, basestring)
        assert os.path.isfile(p)
        assert os.stat(p).st_size > 0
        assert p == self.imagedb.getDiskPath(u'Shut the box.jpg', 123)
        
        url = self.imagedb.getURL(u'Shut the box.jpg')
        assert url == 'http://upload.wikimedia.org/wikipedia/de/3/35/Shut_the_box.jpg'
    
