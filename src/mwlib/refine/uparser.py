# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.


from mwlib import expander, metabook, nshandling
from mwlib.log import Log
from mwlib.parser.old_uparser import postprocessors
from mwlib.refine import compat
from mwlib.utoken import show

log = Log("refine.uparser")


def get_article_raw_text(wikidb, title: str):
    page = wikidb.normalize_and_get_page(title, 0)
    return page.rawtext if page else None


def process_expander_and_siteinfo(wikidb, title, raw, expand_templates):
    te = uniquifier = siteinfo = None
    _input = raw
    if expand_templates:
        te = expander.Expander(raw, pagename=title, wikidb=wikidb)
        uniquifier = te.uniquifier
        _input = te.expandTemplates(True)
    if hasattr(wikidb, "get_siteinfo"):
        siteinfo = wikidb.get_siteinfo()
    return te, uniquifier, siteinfo, _input


def parse_string(
    title=None,
    raw=None,
    wikidb=None,
    revision=None,
    lang=None,
    magicwords=None,
    expand_templates=True,
):
    """parse article with title from raw mediawiki text"""
    te = uniquifier = siteinfo = None
    if title is None:
        raise ValueError("no title given")
    raw = get_article_raw_text(wikidb, title) if raw is None else raw
    if raw is None:
        raise ValueError(f"cannot get article {title!r}")
    _input = raw

    if wikidb:
        te, uniquifier, siteinfo, _input = process_expander_and_siteinfo(
            wikidb, title, raw, expand_templates
        )

        src = None
        if hasattr(wikidb, "getSource"):
            src = wikidb.getSource(title, revision=revision)
            if isinstance(src, dict):
                raise ValueError("wikidb.getSource returned a dict. this is no longer supported")

        if not src:
            src = metabook.source()

        if lang is None:
            lang = src.language
        if magicwords is None:
            if siteinfo is not None and "magicwords" in siteinfo:
                magicwords = siteinfo["magicwords"]
            else:
                magicwords = src.get("magicwords")

    if siteinfo is None:
        nshandler = nshandling.get_nshandler_for_lang(lang)
    else:
        nshandler = nshandling.nshandler(siteinfo)
    a = compat.parse_txt(
        _input,
        title=title,
        wikidb=wikidb,
        nshandler=nshandler,
        lang=lang,
        magicwords=magicwords,
        uniquifier=uniquifier,
        expander=te,
    )

    a.caption = title
    if te and te.magic_displaytitle:
        a.caption = te.magic_displaytitle

    for x in postprocessors:
        x(a, title=title, revision=revision, wikidb=wikidb, lang=lang)

    return a


def simpleparse(raw, lang=None):  # !!! USE FOR DEBUGGING ONLY !!! does not use post processors
    a = compat.parse_txt(raw, lang=lang)
    show(a)
    return a
