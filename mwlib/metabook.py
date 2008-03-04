#! /usr/bin/env python
#! -*- coding:utf-8 -*-

import re
import simplejson

"""
See METABOOK.txt for description of Metabook data
"""

class MetaBook(object):
    """Encapsulate meta information about an article collection"""

    title = u""
    subtitle = u""
    
    def __init__(self):
        self.type = 'collection'
        self.version = 1
        self.items = []
    
    def addArticles(self, articleTitles, chapterTitle=None, contentType='text/x-wiki'):
        """
        @param articleTitles: sequence of article titles or dicts containing
            article title (value for key 'title') and optionally display title
            (value for key 'displaytitle').
        @type articleTitles: [unicode|{str: unicode}]
        """
        
        articles = []
        for title in articleTitles:
            article = {
                'type': 'article',
                'content-type': contentType,
            }
            if isinstance(title, dict):
                article.update(title)
            else:
                article['title'] = title
            articles.append(article)
        if chapterTitle:
            self.items.append({
                'type': 'chapter',
                'title': chapterTitle,
                'items': articles,
            })
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
    
