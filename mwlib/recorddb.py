#! /usr/bin/env python

# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.

class RecordDB(object):
    """Proxy getRawArticle() and getTemplate() to another WikiDB and record all
    results for later retrieval.
    """
    
    def __init__(self, db, articles, templates, sources):
        """
        @param db: WikiDB to use
        
        @param articles: dictionary to store article data
        @type articles: dict
        
        @param templates: dictionary to store template data
        @type templates: dict
        
        @param sources: dictionary to store source data
        @type sources: dict
        """
        
        assert db is not None, "db must not be None"
        self.db = db
        self.articles = articles
        self.templates = templates
        self.sources = sources
    
    def getRawArticle(self, name, revision=None):
        r = self.db.getRawArticle(name, revision=revision)
        if r is None:
            return None
        self.articles[name] = {
            'revision': revision,
            'content-type': 'text/x-wiki',
            'content': r,
            'url': self.db.getURL(name, revision=revision),
            'authors': self.db.getAuthors(name, revision=revision),
        }
        if hasattr(self.db, 'getSource'):
            src  = self.db.getSource(name, revision=revision)
            if src and 'url' in src:
                self.articles[name]['source-url'] = src['url']
                if src['url'] not in self.sources:
                    self.sources[src['url']] = src
        return r
    
    def getTemplate(self, name, followRedirects=False):
        try:
            return self.templates[name]['content']
        except KeyError:
            pass
        r = self.db.getTemplate(name, followRedirects=followRedirects)
        self.templates[name] = {
            'content-type': 'text/x-wiki',
            'content': r,
        }
        return r
    
    def getSource(self, title, revision=None):
        return self.db.getSource(title, revision=revision)
    
