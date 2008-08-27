#! /usr/bin/env py.test
# -*- coding: utf-8 -*-

import os
import shutil
import tempfile
from zipfile import ZipFile

from mwlib import zipcreator, wiki, metabook

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
    
    def getSource(self, name, revision=None):
        return {}
    

class TestZipCreator(object):
    def setup_method(self, method):
        self.fakedb = FakeDB()
        self.tempdir = tempfile.mkdtemp()
        self.zf = ZipFile(os.path.join(self.tempdir, 'test.zip'), 'w')
        self.creator = zipcreator.ZipCreator(self.zf, self.fakedb)
    
    def teardown_method(self, method):
        self.zf.close()
        shutil.rmtree(self.tempdir)
    
    def test_addArticle(self):
        self.creator.addArticle(u'article1', wikidb=self.fakedb, imagedb=None)
        self.creator.join()
        assert u'template1' in self.creator.templates
    
    def test_addObject(self):
        self.creator.addObject(u'fü', 'bär')
    
    def test_writeContent(self):
        self.creator.join()
    
class TestMakeZIPFile(object):
    def setup_method(self, method):
        fd, self.filename = tempfile.mkstemp()
        os.close(fd)
    
    def teardown_mehod(self, method):
        os.unlink(self.filename)
    
    def test_with_metabok(self):
        mb = metabook.make_metabook()
        mb['items'].append(metabook.make_article('Test'))
        env = wiki.makewiki(':en', mb)
        f = zipcreator.make_zip_file(self.filename, env)
        assert f == self.filename
    
