#! /usr/bin/env python

# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

import logging
from collections.abc import Callable
from typing import Optional

from mwlib import parser

log = logging.getLogger('mwlib.writerbase')


class WriterError(RuntimeError):
    pass


def handle_chapter(item, book):
    chapter = parser.Chapter(item.title.strip())
    book.append_child(chapter)
    return chapter


def handle_article(item, env, last_chapter, progress, status_callback):
    wiki_obj = item._env.wiki if item._env else env.wiki

    article = wiki_obj.get_parsed_article(title=item.title, revision=item.revision)
    if article is not None:
        article = update_article_attributes(article, item, wiki_obj)
        if last_chapter:
            last_chapter.append_child(article)
        else:
            env.book.append_child(article)
    else:
        log.warn('No such article: %r' % item.title)
    status_callback(status='parsing', progress=progress, article=item.title)


def update_article_attributes(article, item, wiki_obj):
    if item.displaytitle is not None:
        article.caption = item.displaytitle
    url = wiki_obj.get_url(item.title, item.revision)
    article.url = url if url else None
    source = wiki_obj.get_source(item.title, item.revision)
    article.wikiurl = source.url if source else None
    article.authors = wiki_obj.get_authors(item.title, revision=item.revision)
    return article


def build_book(env, status_callback: Callable[..., None] | None = None):
    env.book = parser.Book()
    progress = 0
    if status_callback is None:
        def status_callback(**kwargs):
            return None

    num_articles = float(len(env.metabook.get_articles()))
    if num_articles > 0:
        progress_step = 100 / num_articles

    last_chapter = None
    for item in env.metabook.walk():
        if item.type == 'Chapter':
            last_chapter = handle_chapter(item, env.book)
        elif item.type == 'article':
            progress += progress_step
            handle_article(item, env, last_chapter, progress, status_callback)

    status_callback(status='parsing', progress=progress, article='')
    return env.book
