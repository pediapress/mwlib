#! /usr/bin/env python

# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

from typing import Callable, Optional
import urllib.request
import urllib.parse
import urllib.error

from mwlib import parser, log, metabook, wiki

# import functions needed by most writers that should be accessible through writerbase
from mwlib.mathutils import renderMath

log = log.Log('mwlib.writerbase')


class WriterError(RuntimeError):
    pass


def handle_chapter(item, book):
    chapter = parser.Chapter(item.title.strip())
    book.append_child(chapter)
    return chapter


def handle_article(item, env, last_chapter, progress, status_callback):
    wiki_obj = item._env.wiki if item._env else env.wiki

    a = wiki_obj.getParsedArticle(title=item.title, revision=item.revision)
    if a is not None:
        a = update_article_attributes(a, item, wiki_obj)
        if last_chapter:
            last_chapter.append_child(a)
        else:
            env.book.append_child(a)
    else:
        log.warn('No such article: %r' % item.title)
    status_callback(status='parsing', progress=progress, article=item.title)


def update_article_attributes(article, item, wiki_obj):
    if item.displaytitle is not None:
        article.caption = item.displaytitle
    url = wiki_obj.getURL(item.title, item.revision)
    article.url = url if url else None
    source = wiki_obj.getSource(item.title, item.revision)
    article.wikiurl = source.url if source else None
    article.authors = wiki_obj.getAuthors(item.title, revision=item.revision)
    return article


def build_book(env, status_callback: Optional[Callable[..., None]] = None):
    env.book = parser.Book()
    progress = 0
    if status_callback is None:
        status_callback = lambda **kwargs: None

    num_articles = float(len(env.metabook.articles()))
    if num_articles > 0:
        progress_step = 100 / num_articles

    last_chapter = None
    for item in env.metabook.walk():
        if item.type == 'chapter':
            last_chapter = handle_chapter(item, env.book)
        elif item.type == 'article':
            progress += progress_step
            handle_article(item, env, last_chapter, progress, status_callback)

    status_callback(status='parsing', progress=progress, article='')
    return env.book
