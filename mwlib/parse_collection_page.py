import os, re, binascii
from collections import defaultdict
from mwlib import metabook, expander

uniq = "--%s--" % binascii.hexlify(os.urandom(16))

def extract_metadata(raw, fields, template_name="saved_book"):
    fields = list(fields)
    fields.append("")

    templ = "".join(u"%s%s\n{{{%s|}}}\n" % (uniq, f, f) for f in fields)
    db = expander.DictDB({template_name:templ})

    te = expander.Expander(raw, pagename="", wikidb=db)
    res = te.expandTemplates()

    d = defaultdict(unicode)
    for x in res.split(uniq)[1:-1]:
        name, val = x.split("\n", 1)
        val = val.strip()
        d[name] = val

    return d



def _buildrex():
    title_rex = '^==(?P<title>[^=].*?[^=])==$'
    subtitle_rex = '^===(?P<subtitle>[^=].*?[^=])===$'
    chapter_rex = '^;(?P<chapter>.+?)$'
    article_rex = '^:\[\[:?(?P<article>.+?)(?:\|(?P<displaytitle>.*?))?\]\]$'
    oldarticle_rex = '^:\[\{\{fullurl:(?P<oldarticle>.+?)\|oldid=(?P<oldid>.*?)\}\}(?P<olddisplaytitle>.*?)\]$'
    template_rex = '^\{\{(?P<template>.*?)\}\}$'
    template_start_rex = '^(?P<template_start>\{\{)$'
    template_end_rex = '.*?(?P<template_end>\}\})$'
    summary_rex = '(?P<summary>.*)'
    alltogether_rex = re.compile("(%s)|(%s)|(%s)|(%s)|(%s)|(%s)|(%s)|(%s)|(%s)" % (
        title_rex, subtitle_rex, chapter_rex, article_rex, oldarticle_rex,
        template_rex, template_start_rex, template_end_rex, summary_rex,
    ))
    return alltogether_rex


alltogether_rex = _buildrex()

def parse_collection_page(wikitext):
    """Parse wikitext of a MediaWiki collection page created by the Collection
    extension for MediaWiki.
    
    @param wikitext: wikitext of a MediaWiki collection page
    @type mwcollection: unicode
    
    @returns: metabook.collection
    @rtype: metabook.collection
    """
    mb = metabook.collection()

    
    summary = False
    noTemplate = True
    for line in wikitext.splitlines():
        line = line.strip()
        if not line:
            continue
        res = alltogether_rex.search(line)
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
            pass
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
