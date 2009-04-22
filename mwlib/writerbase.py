#! /usr/bin/env python

# Copyright (c) 2007-2009 PediaPress GmbH
# See README.txt for additional licensing information.

import urllib

from mwlib import parser, log, metabook, zipwiki, wiki

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
        
    num_articles = float(len(metabook.get_item_list(env.metabook,
        filter_type='article',
    )))
    if num_articles > 0:
        progress_step = 100/num_articles
        
    lastChapter = None
    for item in metabook.get_item_list(env.metabook):
        if item['type'] == 'chapter':
            chapter = parser.Chapter(item['title'].strip())
            book.appendChild(chapter)
            lastChapter = chapter
        elif item['type'] == 'article':
            status_callback(
                status='parsing',
                progress=progress,
                article=item['title'],
            )
            progress += progress_step
            a = env.wiki.getParsedArticle(
                title=item['title'],
                revision=item.get('revision'),
            )
            if a is not None:
                if "displaytitle" in item:
                    a.caption = item['displaytitle']
                url = env.wiki.getURL(item['title'], item.get('revision'))                
                if url:
                    a.url = url
                else:
                    a.url = None
                source = env.wiki.getSource(item['title'], item.get('revision'))
                if source:
                    a.wikiurl = source.get('url', '')
                else:
                    a.wikiurl = None
                a.authors = env.wiki.getAuthors(item['title'], revision=item.get('revision'))
                if lastChapter:
                    lastChapter.appendChild(a)
                else:
                    book.appendChild(a)
            else:
                log.warn('No such article: %r' % item['title'])

    status_callback(status='parsing', progress=progress, article='')
    return book


def build_book_from_zip(zip_filename):
    env = wiki.makewiki(zip_filename)
    env.wiki = zipwiki.Wiki(zip_filename)
    env.images = zipwiki.ImageDB(zip_filename)
    return build_book(env)
