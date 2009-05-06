#! /usr/bin/env python

import re
import StringIO
try:
    from hashlib import md5
except ImportError:
    from md5 import md5

from mwlib import utils

# ==============================================================================

METABOOK_VERSION = 1

# ==============================================================================

def make_metabook(title=None, subtitle=None):
    metabook = {
        'type': 'collection',
        'version': METABOOK_VERSION,
        'summary': '',
        'items': [],
        
    }
    if title:
        metabook['title'] = title
    if subtitle:
        metabook['subtitle'] = subtitle
    return metabook

def make_source(name=None, url=None, language=None, base_url=None, script_extension=None):
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
    if base_url:
        source['base_url'] = base_url
    if script_extension:
        source['script_extension'] = script_extension
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
    oldarticle_rex = '^:\[\{\{fullurl:(?P<oldarticle>.*?)\|oldid=(?P<oldid>.*?)\}\}(?P<olddisplaytitle>.*?)\]$'
    template_rex = '^\{\{(?P<template>.*?)\}\}$'
    template_start_rex = '^(?P<template_start>\{\{)$'
    template_end_rex = '.*?(?P<template_end>\}\})$'
    summary_rex = '(?P<summary>.*)'
    alltogether_rex = re.compile("(%s)|(%s)|(%s)|(%s)|(%s)|(%s)|(%s)|(%s)|(%s)" % (
        title_rex, subtitle_rex, chapter_rex, article_rex, oldarticle_rex,
        template_rex, template_start_rex, template_end_rex, summary_rex,
    ))
    
    summary = False
    noTemplate = True
    firstSummaryLine = True
    for line in wikitext.splitlines():
        if line == "": 
            continue #drop empty lines
        res = alltogether_rex.search(line.strip())
        if not res:
            continue
        
        #look for initial templates and summaries
        #multilinetemplates need different handling to those that fit into one line
        if res.group('template_end') or res.group('template'):
            summary = True
            noTemplate = False
        elif res.group('template_start'):
            noTemplate = False
        elif res.group('summary'):
            if firstSummaryLine:
                firstSummaryLine = False
        else:
            summary = False
            noTemplate = False

        if res.group('title'):
            metabook['title'] = res.group('title')
        elif res.group('subtitle'):
            metabook['subtitle'] = res.group('subtitle')
        elif res.group('chapter'):
            metabook['items'].append(make_chapter(
                title=res.group('chapter').strip(),
            ))
        elif res.group('article'):
            append_article(res.group('article'), res.group('displaytitle'), metabook)
        elif res.group('oldarticle'):
            append_article(res.group('oldarticle'), res.group('olddisplaytitle'), metabook, res.group('oldid'))
        elif res.group('summary') and (noTemplate or summary):
            metabook['summary'] += res.group('summary') + " "
            
    return metabook

def append_article(article, displaytitle, metabook, revision=None):
    if revision:
        article = make_article(title=article.strip(), revision=revision)
    else:
        article = make_article(title=article.strip())
    if displaytitle:
        article['displaytitle'] = displaytitle.strip()
    if metabook['items'] and metabook['items'][-1]['type'] == 'chapter':
        metabook['items'][-1]['items'].append(article)
    else:
        metabook['items'].append(article)

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
            result.extend(get_item_list(item, filter_type=filter_type))
    return result

def calc_checksum(metabook):
    sio = StringIO.StringIO()
    sio.write(repr(metabook.get('title')))
    sio.write(repr(metabook.get('subtitle')))
    sio.write(repr(metabook.get('editor')))
    for item in get_item_list(metabook):
        sio.write(repr(item.get('type')))
        sio.write(repr(item.get('title')))
        sio.write(repr(item.get('displaytitle')))
        sio.write(repr(item.get('revision')))
    return md5(sio.getvalue()).hexdigest()
    
def get_licenses(metabook):
    """Return list of licenses
    
    @returns: list of dicts with license info
    @rtype: [dict]
    """
    
    if 'licenses' not in metabook:
        return []
    
    licenses = []
    for license in metabook['licenses']:
        wikitext = ''

        if license.get('mw_license_url'):
            url = license['mw_license_url']
            if re.match(r'^.*/index\.php.*action=raw', url) and 'templates=expand' not in url:
                url += '&templates=expand'
            wikitext = utils.fetch_url(url,
                ignore_errors=True,
                expected_content_type='text/x-wiki',
            )
            if wikitext:
                try:
                    wikitext = unicode(wikitext, 'utf-8')
                except UnicodeError:
                    wikitext = None
        else:
            wikitext = ''
            if license.get('mw_rights_text'):
                wikitext = license['mw_rights_text']
            if license.get('mw_rights_page'):
                wikitext += '\n\n[[%s]]' % license['mw_rights_page']
            if license.get('mw_rights_url'):
                wikitext += '\n\n' + license['mw_rights_url']
        
        if not wikitext:
            continue
        
        licenses.append({
            'title': license.get('name', u'License'),
            'wikitext': wikitext,
        })
    
    return licenses
    
