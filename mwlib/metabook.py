#! /usr/bin/env python
#! -*- coding:utf-8 -*-

import re
import simplejson

"""
{
    'type': 'collection',
    'version': COLLECTION FORMAT VERSION, # an integer value, 1 for now
    'title': 'COLLECTION TITLE',
    'subtitle': 'COLLECTION SUBTITLE', # optional
    'editor': 'COLLECTION EDITOR', # optional
    'items': [
        {
            'type': 'chapter',
            'title': 'CHAPTER TITLE',
            'items': [
                {
                    'type': 'article',
                    'title': 'ARTICLE TITLE',   
                    'revision': 'ARTITLE REVISION', # e.g. oldid for MediaWiki articles
                },
            ],
            ...
        },
    ],
    'source': {
        'name': 'UNIQUE NAME OF WIKI', # e.g. 'Wikipedia EN'
        'url': 'UNIQUE URL OF WIKI', # e.g. 'http://en.wikipedia.org/wiki/'
    },
}
"""

class MetaBook(object):
    """Encapsulate meta information about an article collection"""
    
    def __init__(self):
        self.type = 'collection'
        self.version = 1
        self.items = []
    
    def addArticles(self, articleTitles, chapterTitle=None, format='text/x-wiki'):
        articles = []
        for title in articleTitles:
            articles.append({
                'type': 'article',
                'title': title
            })
        if chapterTitle:
            self.items.append({
                'type': 'chapter',
                'title': chapterTitle,
                'items': articles,
            })
            self.items.append(chapter)
        else:
            self.items.extend(articles)
    
    def dumpJson(self):
        return simplejson.dumps(vars(self))

    def loadJson(self, jsonStr):
        for (var, value) in simplejson.loads(jsonStr).items():
            setattr(self, var, value)
    
    def readJsonFile(self, filename):
        self.loadJson(open(filename, 'rb').read())
    
    def loadCollectionPage(self, mwcollection):
        """Parse wikitext of a MediaWiki collection page
        
        @param mwcollection: wikitext of a MediaWiki collection page as created by
            the Collection extension for MediaWiki
        @type mwcollection: unicode
        """
        
        titleRe = '^==\s+(?P<title>.*?)\s+==$'
        subtitleRe = '^===\s+(?P<subtitle>.*?)\s+===$'
        chapterRe = '^;(?P<chapter>.*?)$'
        articleRe = '^:\[\[:?(?P<article>.*?)(?:\|(?P<displaytitle>.*?))?\]\]$'
        alltogetherRe = re.compile("(%s)|(%s)|(%s)|(%s)" % (titleRe, subtitleRe, chapterRe, articleRe))
        gotChapter = False
        chapter = ''
        articles =  []
        for line in mwcollection.splitlines():
            res = alltogetherRe.search(line.strip())
            if not res:
                continue
            if res.group('title'):
                self.title = res.group('title')
            elif res.group('subtitle'):
                self.subtitle = res.group('subtitle')
            elif res.group('chapter'):
                self.addArticles(articles, chapter)
                articles = []
                chapter = res.group('chapter')
            elif res.group('article'):
                d = {'title': res.group('article')}
                if res.group('displaytitle'):
                    d['displaytitle'] = res.group('displaytitle')
                articles.append(d)
        
        if len(articles):
            self.addArticles(articles, chapter)
    
    def getArticles(self):
        """Generator that produces a sequence of (title, revision) pairs for
        each article contained in this collection. If no revision is specified,
        None is returned for the revision item.
        """
        
        for item in self.getItems():
            if item['type'] == 'article':
                yield item['title'], item.get('revision', None)
    
    def getItems(self):
        """Generator that produces a flattened list of chapters and articles
        in this collection.
        """
        
        for item in self.items:
            if item['type'] == 'article':
                yield item
            elif item['type'] == 'chapter':
                yield item
                for article in item.get('items', []):
                    yield article
    
