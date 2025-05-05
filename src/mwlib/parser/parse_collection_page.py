import binascii
import os
import re
from collections import defaultdict

from mwlib.core import metabook
from mwlib.parser import expander

uniq = "--%s--" % binascii.hexlify(os.urandom(16))


def extract_metadata(raw, fields, template_name="saved_book"):
    fields = list(fields)
    fields.append("")

    templ = "".join(f"{uniq}{f}\n{{{{{{{f}|}}}}}}\n" for f in fields)
    database = expander.DictDB({template_name: templ})

    template = expander.Expander(raw, pagename="", wikidb=database)
    res = template.expandTemplates()

    metadata = defaultdict(str)
    for segment in res.split(uniq)[1:-1]:
        name, val = segment.split("\n", 1)
        val = val.strip()
        metadata[name] = val

    return metadata


def _buildrex():
    title_rex = "^==(?P<title>[^=].*?[^=])==$"
    subtitle_rex = "^===(?P<subtitle>[^=].*?[^=])===$"
    chapter_rex = "^;(?P<chapter>.+?)$"
    article_rex = r"^:\[\[:?(?P<article>.+?)(?:\|(?P<displaytitle>.*?))?\]\]$"
    oldarticle_rex = r"^:\[\{\{fullurl:(?P<oldarticle>.+?)\|oldid=(?P<oldid>.*?)\}\}(?P<olddisplaytitle>.*?)\]$"
    template_rex = r"^\{\{(?P<template>.*?)\}\}$"
    template_start_rex = r"^(?P<template_start>\{\{)$"
    template_end_rex = r".*?(?P<template_end>\}\})$"
    summary_rex = "(?P<summary>.*)"
    alltogether_rex = re.compile(
        f"({title_rex})|({subtitle_rex})|({chapter_rex})|({article_rex})|({oldarticle_rex})|({template_rex})|({template_start_rex})|({template_end_rex})|({summary_rex})"
    )
    return alltogether_rex


alltogether_rex = _buildrex()


def _update_meta_book_from_regex_match(res, meta_book, no_template, summary):
    if res.group("title"):
        meta_book.title = res.group("title").strip()
    elif res.group("subtitle"):
        meta_book.subtitle = res.group("subtitle").strip()
    elif res.group("chapter"):
        meta_book.items.append(metabook.Chapter(title=res.group("chapter").strip()))
    elif res.group("article"):
        meta_book.append_article(res.group("article"), res.group("displaytitle"))
    elif res.group("oldarticle"):
        meta_book.append_article(
            title=res.group("oldarticle"),
            displaytitle=res.group("olddisplaytitle"),
            revision=res.group("oldid"),
        )
    elif res.group("summary") and (no_template or summary):
        meta_book.summary += res.group("summary") + " "


def parse_collection_page(wikitext):
    """Parse wikitext of a MediaWiki collection page created by the Collection
    extension for MediaWiki.

    @param wikitext: wikitext of a MediaWiki collection page
    @type mwcollection: unicode

    @returns: metabook.collection
    @rtype: metabook.collection
    """
    meta_book = metabook.Collection()

    summary = False
    no_template = True
    for line in wikitext.splitlines():
        line = line.strip()
        if not line:
            continue
        res = alltogether_rex.search(line)
        if not res:
            continue

        # look for initial templates and summaries
        # multilinetemplates need different handling
        # to those that fit into one line
        if res.group("template_end") or res.group("template"):
            summary = True
            no_template = False
        elif res.group("template_start"):
            no_template = False
        elif res.group("summary"):
            pass
        else:
            summary = False
            no_template = False

        _update_meta_book_from_regex_match(res, meta_book, no_template, summary)

    return meta_book
