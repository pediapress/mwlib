# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

import contextlib
import os

import gevent
import gevent.pool
import six
import six.moves.urllib.error
import six.moves.urllib.parse
import six.moves.urllib.request

from mwlib.metabook import collection, get_licenses, parse_collection_page
from mwlib.net import fetch
from mwlib.net import sapi as mwapi
from mwlib.parser.parse_collection_page import extract_metadata
from mwlib.utilities import myjson


class StartFetcher:
    progress = None

    def __init__(self, **kw):
        self.fetcher = None
        self.__dict__.update(kw)
        self.nfo = {}

    def get_api(self):
        if self.username:
            api = mwapi.MwApi(self.api_url, self.username, self.password)
        else:
            api = mwapi.MwApi(self.api_url)
        api.set_limit()

        if self.username:
            api.login(self.username, self.password, self.domain)
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
                "script_extension": self.options.script_extension,
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
            imagesize=self.options.imagesize,
            cover_image=metabook.cover_image,
            fetch_images=not self.options.noimages,
        )
        self.fetcher.run()

    def init_variables(self):
        base_url = self.base_url
        options = self.options

        if not base_url.endswith("/"):
            base_url += "/"
        api_url = "".join([base_url, "api", options.script_extension])
        self.api_url = api_url

        self.username = options.username
        self.password = options.password
        self.domain = options.domain

        self.fsout = fetch.FsOutput(self.fsdir)

    def fetch_collectionpage(self, api):
        collection_page = self.options.collectionpage
        if collection_page is None:
            return api

        with contextlib.suppress(Exception):
            collection_page = six.text_type(six.moves.urllib.parse.unquote(str(collection_page)),
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
        if isinstance(rawtext, six.text_type):
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

    for article in metabook.articles():
        if article.revision:
            continue

        try:
            rev = trust_revisions.get_trusted_revision(x.title)
            article.revision = rev["revid"]

            print(
                "chosen trusted revision: title=%-20r age=%6.1fd revid=%10d user=%-20r"
                % (rev["title"], rev["age"], rev["revid"], rev["user"])
            )
        except Exception as err:
            print("error choosing trusted revision for",
                  repr(article.title), repr(err))


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
        my_mb = collection()
        my_mb.items = articles
    else:
        my_mb = metabook
    return my_mb


def get_id_wikis(metabook):
    id2wiki = {}
    for wiki in metabook.wikis:
        id2wiki[wiki.ident] = (wiki, [])

    for wiki in metabook.articles():
        if wiki.wikiident not in id2wiki:
            raise ValueError(f"no wikiconf for {wiki.wikiident!r} ({wiki})")
        id2wiki[wiki.wikiident][1].append(wiki)
    return id2wiki


def make_nuwiki(fsdir, metabook, options, podclient=None, status=None):
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

        wikitrust(wikiconf.baseurl, my_mb)

        fetchers.append(
            StartFetcher(
                fsdir=my_fsdir,
                progress=progress,
                base_url=wikiconf.baseurl,
                metabook=my_mb,
                options=options,
                podclient=podclient,
                status=status,
            )
        )

    if is_multiwiki:
        write_multi_wiki_metabook(fsdir, metabook)

    start_fetchers(fetchers)
