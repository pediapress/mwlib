#! /usr/bin/env python

# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

import urllib

from mwlib import parser, log, metabook, wiki

# import functions needed by most writers that should be accessible through writerbase
from mwlib.mathutils import renderMath

log = log.Log('mwlib.writerbase')

class WriterError(RuntimeError):
    pass

def build_book(env, status_callback=None):
    book = parser.Book()
    progress = 0
    if status_callback is None:
        status_callback = lambda **kwargs: None
        
    num_articles = float(len(env.metabook.articles()))
    if num_articles > 0:
        progress_step = 100/num_articles
        
    lastChapter = None
    for item in env.metabook.walk():
        if item.type == 'chapter':
            chapter = parser.Chapter(item.title.strip())
            book.appendChild(chapter)
            lastChapter = chapter
        elif item.type == 'article':
            status_callback(status='parsing', progress=progress, article=item.title)
            progress += progress_step

            if item._env:
                wiki = item._env.wiki
            else:
                wiki = env.wiki
            
            a = wiki.getParsedArticle(title=item.title, revision=item.revision)
            
            if a is not None:
                if item.displaytitle is not None:
                    a.caption = item.displaytitle
                url = wiki.getURL(item.title, item.revision)                
                if url:
                    a.url = url
                else:
                    a.url = None
                source = wiki.getSource(item.title, item.revision)
                if source:
                    a.wikiurl = source.url
                else:
                    a.wikiurl = None
                    
                a.authors = wiki.getAuthors(item.title, revision=item.revision)
                if lastChapter:
                    lastChapter.appendChild(a)
                else:
                    book.appendChild(a)
            else:
                log.warn('No such article: %r' % item.title)

    status_callback(status='parsing', progress=progress, article='')
    return book
