#! /usr/bin/env py.test
# -*- coding: utf-8 -*-

from mwlib import recorddb, wikidbbase

norm = wikidbbase.normalize_title

class FakeDB(object):
    articles = {
        u'Article1': {
            'text': u'article text [[Image:Test.jpg]] {{template1}}',
            'url': 'http://some/url/',
        },
    }
    templates = {
        u'Template1': u'template text',
    }
    def getRawArticle(self, title, revision=None):
        try:
            return self.articles[norm(title)]['text']
        except KeyError:
            return None
    
    def getTemplate(self, title, followRedirects=False):
        try:
            return self.templates[norm(title)]
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
