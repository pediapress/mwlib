#! /usr/bin/env py.test
# -*- coding: utf-8 -*-

import os
import shutil
import tempfile
from zipfile import ZipFile

from mwlib import recorddb

class FakeDB(object):
    articles = {
        u'article1': {
            'text': u'article text [[Image:Test.jpg]] {{template1}}',
            'url': 'http://some/url/',
        },
    }
    templates = {
        u'template1': u'template text',
    }
    def getRawArticle(self, title, revision=None):
        try:
            a = self.articles[title]
        except KeyError:
            return None
        return a['text']
    
    def getTemplate(self, title, followRedirects=False):
        try:
            return self.templates[title]
        except KeyError:
            return None
    
    def getURL(self, title, revision=None):
        try:
            a = self.articles[title]
        except KeyError:
            return None
        return a['url']
    
    def getAuthors(self, title, revision=None):
        try:
            a = self.articles[title]
        except KeyError:
            return None
        return [u'foo', u'bar']
    

class TestRecordDB(object):
    def setup_method(self, method):
        self.fakedb = FakeDB()
        self.articles = {}
        self.templates = {}
        self.recorddb = recorddb.RecordDB(self.fakedb, self.articles, self.templates)
    
    def test_getRawArticle(self):
        raw = self.recorddb.getRawArticle(u'article1')
        assert isinstance(raw, unicode)
        assert len(self.articles) == 1
    
    def test_getTemplate(self):
        raw = self.recorddb.getTemplate(u'template1')
        assert isinstance(raw, unicode)
        assert len(self.templates) == 1
    

class TestZipFileCreator(object):
    def setup_method(self, method):
        self.fakedb = FakeDB()
        self.tempdir = tempfile.mkdtemp()
        self.zf = ZipFile(os.path.join(self.tempdir, 'test.zip'), 'w')
        self.creator = recorddb.ZipfileCreator(self.zf, self.fakedb)
    
    def teardown_method(self, method):
        self.zf.close()
        shutil.rmtree(self.tempdir)
    
    def test_addArticle(self):
        self.creator.addArticle(u'article1', wikidb=self.fakedb, imagedb=None)
        assert u'template1' in self.creator.templates
    
    def test_addObject(self):
        self.creator.addObject(u'fü', 'bär')
    
    def test_writeContent(self):
        self.creator.writeContent()
    

