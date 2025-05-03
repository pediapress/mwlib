# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

import copy
import re
import warnings
from collections import deque
from hashlib import sha256

from mwlib.parser.parse_collection_page import parse_collection_page
from mwlib.utils import myjson, unorganized


class MbObj:
    def __init__(self, **kw):
        type_names = {"type": self.__class__.__name__}

        for k in dir(self.__class__):
            if k.startswith("__"):
                continue
            value = getattr(self.__class__, k)
            if callable(value) or value is None:
                continue
            if isinstance(value, (property,)):
                continue

            type_names[k] = value
        self.image = None
        self.__dict__.update(copy.deepcopy(type_names))
        self.__dict__.update(kw)
        self.type = self.__class__.__name__

    def __getitem__(self, key):
        warnings.warn(f"deprecated __getitem__ [{key!r}]", DeprecationWarning, 2)

        try:
            return getattr(self, str(key))
        except AttributeError as exc:
            raise KeyError(repr(key)) from exc

    def __setitem__(self, key, val):
        warnings.warn(f"deprecated __setitem__ [{key!r}]=", DeprecationWarning, 2)

        self.__dict__[key] = val

    def __contains__(self, key):
        warnings.warn(f"deprecated __contains__ {key!r} in ", DeprecationWarning, 2)
        val = getattr(self, str(key), None)
        return val is not None

    def get(self, key, default=None):
        warnings.warn(f"deprecated call get({key!r})", DeprecationWarning, 2)
        try:
            val = getattr(self, str(key))
            if val is None:
                return default
            return val
        except AttributeError:
            return default

    def _json(self):
        type_names = {"type": self.__class__.__name__}
        for k, value in self.__dict__.items():
            if value is not None and not k.startswith("_"):
                type_names[k] = value
        return type_names

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.__dict__!r}>"


class WikiConf(MbObj):
    baseurl = None
    ident = None

    def __init__(self, **kw):
        MbObj.__init__(self, **kw)


class collection(MbObj):
    title = None
    subtitle = None
    editor = None
    cover_image = None
    cover_color = None
    text_color = None
    description = None
    sort_as = None

    version = 1
    summary = ""
    items = []
    licenses = []
    wikis = []
    _env = None

    def append_article(self, title, displaytitle=None, **kw):
        title = title.strip()
        if displaytitle is not None:
            displaytitle = displaytitle.strip()
        art = article(title=title, displaytitle=displaytitle, **kw)

        if self.items and isinstance(self.items[-1], Chapter):
            self.items[-1].items.append(art)
        else:
            self.items.append(art)

    def dumps(self):
        return myjson.dumps(self, sort_keys=True, indent=4)

    def walk(self, filter_type=None):
        todo = deque(self.items)
        res = []
        while todo:
            elem = todo.popleft()
            if not filter_type or elem.type == filter_type:
                res.append(elem)
            items = getattr(elem, "items", None)
            if items:
                todo.extendleft(items[::-1])
        return res

    def articles(self):
        return self.walk("article")

    def set_environment(self, env):
        if env.wikiconf:
            self.wikis.append(env.wikiconf)

        for article in self.articles():
            if article._env is None:
                article._env = env

    def get_wiki(self, ident=None, baseurl=None):
        if ident is None and baseurl is None:
            raise ValueError("need ident or baseurl")
        if ident is not None and baseurl is not None:
            raise ValueError("need ident or baseurl, not both")

        for wikiconf in self.wikis:
            if ident is not None and wikiconf.ident == ident:
                return wikiconf
            if baseurl is not None and wikiconf.baseurl == baseurl:
                return wikiconf
        return None


class Source(MbObj):
    name = None
    url = None
    language = None
    base_url = None
    script_extension = None
    locals = None
    system = "MediaWiki"
    namespaces = None


class Interwiki(MbObj):
    local = False


class custom(MbObj):
    title=None
    content=None
    content_type='text/x-wiki'


class article(MbObj):
    title = None
    displaytitle = None
    revision = None
    content_type = "text/x-wiki"
    wikiident = None
    _env = None

    @property
    def wiki(self):
        return self._env.wiki

    @property
    def images(self):
        return self._env.images


class License(MbObj):
    title = None
    wikitext = None


class Chapter(MbObj):
    items = []
    title = ""


# ==============================================================================


def append_article(new_article, displaytitle, metabook, revision=None):
    metabook.append_article(new_article, displaytitle, revision=revision)


def get_item_list(metabook, filter_type=None):
    """Return a flat list of items in given metabook

    @param metabook: metabook dictionary
    @type metabook: dict

    @param filter_type: if set, return only items with this type
    @type filter_type: str

    @returns: flat list of items
    @rtype: [{}]
    """
    return metabook.walk(filter_type=filter_type)


def calc_checksum(metabook):
    return sha256(metabook.dumps().encode("utf-8")).hexdigest()


def get_wiki_text_from_url(license_to_check):
    url = license_to_check["mw_license_url"]
    if (
        re.match(r"^.*/index\.php.*action=raw", url)
        and "templates=expand" not in url
    ):
        url += "&templates=expand"
    wikitext = unorganized.fetch_url(
        url,
        ignore_errors=True,
        expected_content_type="text/x-wiki",
    )
    if wikitext:
        try:
            wikitext = str(wikitext, "utf-8")
        except UnicodeError:
            wikitext = None
    return wikitext


def get_wiki_text_for_license(license_to_check):
    wikitext = ""

    if license_to_check.get("mw_license_url"):
        wikitext = get_wiki_text_from_url(license_to_check)
    else:
        wikitext = ""
        if license_to_check.get("mw_rights_text"):
            wikitext = license_to_check["mw_rights_text"]
        if license_to_check.get("mw_rights_page"):
            mw_rights_page = license_to_check["mw_rights_page"]
            wikitext += f"\n\n[[{mw_rights_page}]]"
        if license_to_check.get("mw_rights_url"):
            wikitext += "\n\n" + license_to_check["mw_rights_url"]

    return wikitext


def get_licenses(metabook):
    """Return list of licenses

    @returns: list of dicts with license info
    @rtype: [dict]
    """
    retval = []
    for license in metabook.licenses:
        wikitext = get_wiki_text_for_license(license)
        if not wikitext:
            continue

        retval.append(License(title=license.get("name", "License"),
                              wikitext=wikitext))

    return retval


def make_interwiki(api_entry=None):
    api_entry = api_entry or {}
    api_entries = {}
    for k, val in api_entry.items():
        api_entries[str(k)] = val
    return Interwiki(**api_entries)
