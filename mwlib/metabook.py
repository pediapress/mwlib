#! /usr/bin/env python

import re

# ==============================================================================

METABOOK_VERSION = 1

# ==============================================================================

def make_metabook(title=None, subtitle=None):
    metabook = {
        'type': 'collection',
        'version': METABOOK_VERSION,
        'items': [],
    }
    if title:
        metabook['title'] = title
    if subtitle:
        metabook['subtitle'] = subtitle
    return metabook

def make_source(name=None, url=None, language=None):
    source = {
        'type': 'source',
        'system': 'MediaWiki',
    }
    if name:
        source['name'] = name
    if url:
        source['url'] = url
    if language:
        source['language'] = language
    return source

def make_interwiki(api_entry=None):
    interwiki = {
        'type': 'interwiki',
    }
    if api_entry is not None:
        interwiki.update(api_entry)
        if 'local' in interwiki:
            interwiki['local'] = True
        else:
            interwiki['local'] = False
    return interwiki

def make_article(title=None, displaytitle=None, revision=None, content_type='text/x-wiki'):
    article = {
        'type': 'article',
        'content-type': content_type,
    }
    if title:
        article['title'] = title
    if displaytitle:
        article['displaytitle'] = displaytitle
    if revision:
        article['revision'] = revision
    return article

def make_chapter(title=None):
    chapter = {
        'type': 'chapter',
        'items': [],
    }
    if title:
        chapter['title'] = title
    return chapter

# ==============================================================================

def parse_collection_page(wikitext):
    """Parse wikitext of a MediaWiki collection page created by the Collection
    extension for MediaWiki.
    
    @param wikitext: wikitext of a MediaWiki collection page
    @type mwcollection: unicode
    
    @returns: metabook dicitonary
    @rtype: dict
    """
    
    metabook = make_metabook()
    
    title_rex = '^==\s+(?P<title>.*?)\s+==$'
    subtitle_rex = '^===\s+(?P<subtitle>.*?)\s+===$'
    chapter_rex = '^;(?P<chapter>.*?)$'
    article_rex = '^:\[\[:?(?P<article>.*?)(?:\|(?P<displaytitle>.*?))?\]\]$'
    alltogether_rex = re.compile("(%s)|(%s)|(%s)|(%s)" % (
        title_rex, subtitle_rex, chapter_rex, article_rex,
    ))
    
    for line in wikitext.splitlines():
        res = alltogether_rex.search(line.strip())
        if not res:
            continue
        if res.group('title'):
            metabook['title'] = res.group('title')
        elif res.group('subtitle'):
            metabook['subtitle'] = res.group('subtitle')
        elif res.group('chapter'):
            metabook['items'].append(make_chapter(
                title=res.group('chapter').strip(),
            ))
        elif res.group('article'):
            article = make_article(title=res.group('article').strip())
            if res.group('displaytitle'):
                article['displaytitle'] = res.group('displaytitle').strip()
            if metabook['items'] and metabook['items'][-1]['type'] == 'chapter':
                metabook['items'][-1]['items'].append(article)
            else:
                metabook['items'].append(article)
    
    return metabook

def get_item_list(metabook, filter_type=None):
    """Return a flat list of items in given metabook
    
    @param metabook: metabook dictionary
    @type metabook: dict
    
    @param filter_type: if set, return only items with this type
    @type filter_type: basestring
    
    @returns: flat list of items
    @rtype: [{}]
    """
    
    result = []
    for item in metabook.get('items', []):
        if not filter_type or item['type'] == filter_type:
            result.append(item)
        if 'items' in item:
            result.extend(get_item_list(item))
    return result
