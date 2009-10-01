import re
from mwlib import metabook

def parse_collection_page(wikitext):
    """Parse wikitext of a MediaWiki collection page created by the Collection
    extension for MediaWiki.
    
    @param wikitext: wikitext of a MediaWiki collection page
    @type mwcollection: unicode
    
    @returns: metabook dictionary
    @rtype: dict
    """
    mb = metabook.collection()

    title_rex = '^==(?P<title>[^=].*?[^=])==$'
    subtitle_rex = '^===(?P<subtitle>[^=].*?[^=])===$'
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
            mb.title = res.group('title').strip()
        elif res.group('subtitle'):
            mb.subtitle = res.group('subtitle').strip()
        elif res.group('chapter'):
            mb.items.append(metabook.chapter(title=res.group('chapter').strip()))
        elif res.group('article'):
            mb.append_article(res.group('article'), res.group('displaytitle'))
        elif res.group('oldarticle'):
            mb.append_article(title=res.group('oldarticle'), displaytitle=res.group('olddisplaytitle'), revision=res.group('oldid'))
        elif res.group('summary') and (noTemplate or summary):
            mb.summary += res.group('summary') + " "

    return mb
