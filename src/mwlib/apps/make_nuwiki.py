# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

import contextlib
import logging
import os
import urllib.parse

import gevent
import gevent.pool

from mwlib.core.metabook import Collection, get_licenses, parse_collection_page
from mwlib.network import fetch
from mwlib.network import sapi as mwapi
from mwlib.parser.parse_collection_page import extract_metadata
from mwlib.utils import myjson

logger = logging.getLogger(__name__)


class StartFetcher:
    progress = None

    def __init__(self, **kw):
        self.fetcher = None
        self.__dict__.update(kw)
        self.nfo = {}

    def get_api(self):
        username = self.wiki_options.get("username")
        password = self.wiki_options.get("password")
        domain = self.wiki_options.get("domain")
        if username:
            api = mwapi.MwApi(self.api_url, username, password)
        else:
            api = mwapi.MwApi(self.api_url)
        api.set_limit()

        if username:
            api.login(username, password, domain)
        return api

    def fetch_pages_from_metabook(self, api):
        fsout = self.fsout
        metabook = self.metabook

        fsout.dump_json(metabook=metabook)
        nfo = self.nfo.copy()

        nfo.update(
            {
                "format": "nuwiki",
                "base_url": self.base_url,
                "script_extension": self.wiki_options.get("script_extension"),
            }
        )

        fsout.nfo = nfo
        pages = fetch.pages_from_metabook(metabook)
        self.fetcher = fetch.Fetcher(
            api,
            fsout,
            pages,
            licenses=self.licenses,
            status=self.status,
            progress=self.progress,
            imagesize=self.wiki_options.get("imagesize"),
            cover_image=metabook.cover_image,
            fetch_images=not self.wiki_options.get("noimages"),
        )
        self.fetcher.run()

    def init_variables(self):
        base_url = self.base_url
        options = self.wiki_options

        if not base_url.endswith("/"):
            base_url += "/"
        script_extension = options.get("script_extension")
        api_url = "".join([base_url, "api", script_extension])
        self.api_url = api_url

        self.username = options.get("username")
        self.password = options.get("password")
        self.domain = options.get("domain")

        self.fsout = fetch.FsOutput(self.fsdir)

    def fetch_collectionpage(self, api):
        collection_page = self.wiki_options.get("collection_page")
        if collection_page is None:
            return api

        with contextlib.suppress(Exception):
            collection_page = str(urllib.parse.unquote(str(collection_page)),
                                            "utf-8")

        self.nfo["collectionpage"] = collection_page

        val = api.fetch_pages([collection_page])
        rawtext = list(val["pages"].values())[0]["revisions"][0]["*"]
        meta_book = self.metabook = parse_collection_page(rawtext)
        wikitrust(api.baseurl, meta_book)

        # XXX: localised template parameter names???
        meta = extract_metadata(
            rawtext,
            (
                "cover-image",
                "cover-color",
                "text-color",
                "editor",
                "description",
                "sort_as",
            ),
        )
        meta_book.editor = meta["editor"]
        meta_book.cover_image = meta["cover-image"]
        meta_book.cover_color = meta["cover-color"]
        meta_book.text_color = meta["text-color"]
        meta_book.description = meta["description"]
        meta_book.sort_as = meta["sort_as"]

        path = os.path.join(self.fsout.path, "collectionpage.txt")
        if isinstance(rawtext, str):
            rawtext = rawtext.encode("utf-8")
        with open(path, "wb") as file:
            file.write(rawtext)
        return api

    def run(self):
        self.init_variables()

        self.licenses = get_licenses(self.metabook)

        api = self.get_api()
        self.fetch_collectionpage(api)
        self.fetch_pages_from_metabook(api)


def wikitrust(baseurl, metabook):
    if not os.environ.get("TRUSTEDREVS"):
        return

    if not baseurl.startswith("http://en.wikipedia.org/w/"):
        return

    from mwlib import trustedrevs

    trust_revisions = trustedrevs.TrustedRevisions()

    for article in metabook.get_articles():
        if article.revision:
            continue

        try:
            rev = trust_revisions.get_trusted_revision(article.title)
            article.revision = rev["revid"]

            print(
                "chosen trusted revision: title=%-20r age=%6.1fd revid=%10d user=%-20r"
                % (rev["title"], rev["age"], rev["revid"], rev["user"])
            )
        except Exception as err:
            print("error choosing trusted revision for", repr(article.title), repr(err))


def write_multi_wiki_metabook(fsdir, metabook):
    if not os.path.exists(fsdir):
        os.makedirs(fsdir)
    with open(os.path.join(fsdir, "metabook.json"), "wb") as metabook_file:
        metabook_file.write(metabook.dumps())
    with open(os.path.join(fsdir, "nfo.json"), "wb") as nfo_file:
        myjson.dump({"format": "multi-nuwiki"}, nfo_file)


def start_fetchers(fetchers):
    pool = gevent.pool.Pool()
    for fetcher in fetchers:
        pool.spawn(fetcher.run)
    pool.join(raise_error=True)

    import signal

    signal.signal(signal.SIGINT, signal.SIG_DFL)
    signal.signal(signal.SIGTERM, signal.SIG_DFL)


def get_metabook(is_multiwiki, articles, metabook):
    if is_multiwiki:
        my_mb = Collection()
        my_mb.items = articles
    else:
        my_mb = metabook
    return my_mb


def get_id_wikis(metabook):
    id2wiki = {}
    for wiki in metabook.wikis:
        id2wiki[wiki.ident] = (wiki, [])
    for wiki in metabook.get_articles():
        if wiki.wikiident not in id2wiki:
            raise ValueError(f"no wikiconf for {wiki.wikiident!r} ({wiki})")
        id2wiki[wiki.wikiident][1].append(wiki)
    return id2wiki


def make_nuwiki(
    fsdir,
    metabook,
    wiki_options,
    pod_client,
    status,
):
    logger.info("making nuwiki")
    id2wiki = get_id_wikis(metabook)

    is_multiwiki = len(id2wiki) > 1

    progress = fetch.SharedProgress(status=status) if is_multiwiki else None

    fetchers = []
    for _id, (wikiconf, articles) in id2wiki.items():
        if _id is None:
            _id = ""
            if is_multiwiki:
                raise ValueError("id must be set in multiwiki")

        if not is_multiwiki:
            _id = ""
        if "/" in _id:
            raise ValueError(f"bad id: {_id!r}")
        my_fsdir = os.path.join(fsdir, _id)

        my_mb = get_metabook(is_multiwiki, articles, metabook)

        wikitrust(wikiconf.baseurl, my_mb) # TODO: doesn't seem to work anymore

        fetchers.append(
            StartFetcher(
                fsdir=my_fsdir,
                progress=progress,
                base_url=wikiconf.baseurl,
                metabook=my_mb,
                wiki_options=wiki_options,
                pod_client=pod_client,
                status=status,
            )
        )

    if is_multiwiki:
        write_multi_wiki_metabook(fsdir, metabook)

    start_fetchers(fetchers)
