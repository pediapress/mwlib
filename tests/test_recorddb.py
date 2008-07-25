#! /usr/bin/env py.test
# -*- coding: utf-8 -*-

import os
import shutil
import tempfile
from zipfile import ZipFile

from mwlib import recorddb, wiki, metabook

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
            return self.articles[title]['text']
        except KeyError:
            return None
    
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
        self.sources = {}
        self.recorddb = recorddb.RecordDB(self.fakedb, self.articles, self.templates, self.sources)
    
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
        self.creator.article_adders.join()
        assert u'template1' in self.creator.templates
    
    def test_addObject(self):
        self.creator.addObject(u'fü', 'bär')
    
    def test_writeContent(self):
        self.creator.writeContent()
    
class TestMakeZIPFile(object):
    class Options(object):
        no_threads = False
        imagesize = 800
        
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)
    
    def setup_method(self, method):
        fd, self.filename = tempfile.mkstemp()
        os.close(fd)
    
    def teardown_mehod(self, method):
        os.unlink(self.filename)
    
    def test_with_metabok(self):
        mb = metabook.make_metabook()
        mb['items'].append(metabook.make_article('Test'))
        env = wiki.makewiki(':en', mb)
        f = recorddb.make_zip_file(self.filename, env)
        assert f == self.filename
    
