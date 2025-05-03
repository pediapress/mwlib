
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

"""
namespace handling based on data extracted from the siteinfo as
returned by api.php
"""

import re

from mwlib.network import siteinfo

NS_MEDIA = -2
NS_SPECIAL = -1
NS_MAIN = 0
NS_TALK = 1
NS_USER = 2
NS_USER_TALK = 3
NS_PROJECT = 4
NS_PROJECT_TALK = 5
NS_FILE = 6
NS_IMAGE = 6
NS_FILE_TALK = 7
NS_IMAGE_TALK = 7
NS_MEDIAWIKI = 8
NS_MEDIAWIKI_TALK = 9
NS_TEMPLATE = 10
NS_TEMPLATE_TALK = 11
NS_HELP = 12
NS_HELP_TALK = 13
NS_CATEGORY = 14
NS_CATEGORY_TALK = 15


class ILink:
    url = ""
    prefix = ""
    local = ""
    language = ""
    partial = ""


def fix_wikipedia_siteinfo(siteinfo):

    # --- http://code.pediapress.com/wiki/ticket/754

    if '\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd' in [
            x.get("prefix", "")[2:] for x in siteinfo.get("interwikimap", [])]:
        print("WARNING: interwikimap contains garbage")
        eng_locale = siteinfo.get_siteinfo("en")
        siteinfo['interwikimap'] = list(eng_locale["interwikimap"])

    prefixes = [x['prefix'] for x in siteinfo['interwikimap']]
    for prefix in ["pnb", "ckb", "mwl", "mhr", "ace", "krc", "pcd", "frr", "koi", "gag", "bjn", "pfl", "mrj", "bjn", "rue", "kbd", "ltg", "xmf"]:

        if prefix in prefixes:
            return
        siteinfo['interwikimap'].append({
            'prefix': prefix,
            'language': prefix,
            'url': f'http://{prefix}.wikipedia.org/wiki/$1',
            'local': '',
        })



class NsHandler:
    def __init__(self, siteinfo):
        if siteinfo is None:
            raise ValueError("siteinfo is None")

        if 'general' in siteinfo and siteinfo['general'].get('server', '').endswith(
                ".wikipedia.org") and 'interwikimap' in siteinfo:
            fix_wikipedia_siteinfo(siteinfo)

        self.siteinfo = siteinfo
        try:
            self.capitalize = self.siteinfo['general'].get('case') == 'first-letter'
        except KeyError:
            self.capitalize = True

        prefix2_interwiki = self.prefix2interwiki = {}
        for k in siteinfo.get("interwikimap", []):
            prefix2_interwiki[k["prefix"]] = k

        self.set_redirect_matcher(siteinfo)

    def set_redirect_matcher(self, siteinfo):
        self.redirect_matcher = get_redirect_matcher(siteinfo, self)

    def __getstate__(self):
        data = self.__dict__.copy()
        del data['redirect_matcher']
        return data

    def __setstate__(self, data):
        self.__dict__ = data
        self.set_redirect_matcher(self.siteinfo)


    def _find_namespace(self, name, defaultns=0):
        name = name.lower().strip()
        namespaces = list(self.siteinfo["namespaces"].values())
        for namespace in namespaces:
            star = namespace["*"]
            if star.lower() == name or namespace.get("canonical", "").lower() == name:
                return True, namespace["id"], star

        aliases = self.siteinfo.get("namespacealiases", [])
        for alias in aliases:
            if alias["*"].lower() == name:
                nsid = alias["id"]
                return True, nsid, self.siteinfo["namespaces"][str(nsid)]["*"]

        return False, defaultns, self.siteinfo["namespaces"][str(defaultns)]["*"]

    def get_fqname(self, title, defaultns=0):
        return self.splitname(title, defaultns=defaultns)[2]

    def maybe_capitalize(self, tag):
        if self.capitalize:
            return tag[0:1].upper() + tag[1:]
        return tag

    def splitname(self, title, defaultns=0):
        if not isinstance(title, str):
            title = title.decode('utf-8') if isinstance(title, bytes) else str(title)
        name = re.sub(r' +', ' ', title.replace("_", " ").strip())
        if name.startswith(":"):
            name = name[1:].strip()
            defaultns = 0

        if ":" in name:
            namespace, partial_name = name.split(":", 1)
            was_namespace, nsnum, prefix = self._find_namespace(namespace,
                                                                defaultns=defaultns)
            suffix = partial_name.strip() if was_namespace else name
        else:
            prefix = self.siteinfo["namespaces"][str(defaultns)]["*"]
            suffix = name
            nsnum = defaultns

        suffix = suffix.strip("\u200e\u200f")
        suffix = self.maybe_capitalize(suffix)
        if prefix:
            prefix += ":"

        return (nsnum, suffix, f"{prefix}{suffix}")

    def get_nsname_by_number(self, namespace):
        return self.siteinfo["namespaces"][str(namespace)]["*"]

    def resolve_interwiki(self, title):
        name = title.replace("_", " ").strip()
        if name.startswith(":"):
            name = name[1:].strip()
        if ":" not in name:
            return None
        prefix, suffix = name.split(":", 1)
        prefix = prefix.strip().lower()
        data = self.prefix2interwiki.get(prefix)
        if data is None:
            return None

        suffix = suffix.strip(" _\n\t\r").replace(" ", "_")
        retval = ILink()
        retval.__dict__.update(data)
        retval.url = retval.url.replace("$1", suffix)
        retval.partial = suffix
        return retval


def get_nshandler_for_lang(lang):
    if lang is None:
        lang = "de"  # FIXME: we currently need this to make the tests happy
    site_info = siteinfo.get_siteinfo(lang)
    if site_info is None:
        site_info = siteinfo.get_siteinfo("en")
        if not site_info:
            raise ValueError("no siteinfo for en")
    return NsHandler(site_info)


def get_redirect_matcher(siteinfo, handler=None):
    redirect_str = "#REDIRECT"
    magicwords = siteinfo.get("magicwords")
    if magicwords:
        for magic in magicwords:
            if magic['name'] == 'redirect':
                redirect_str = "(?:" + "|".join([re.escape(x) for x in magic['aliases']]) + ")"
    redirect_rex = re.compile(
        r'^[ \t\n\r\0\x0B]*%s\s*:?\s*?\[\[(?P<redirect>.*?)\]\]' % redirect_str, re.IGNORECASE)

    if handler is None:
        handler = NsHandler(siteinfo)

    def redirect(text):
        match_object = redirect_rex.search(text)
        if match_object:
            name = match_object.group('redirect').split("|", 1)[0]
            name = name.split("#")[0]
            return handler.get_fqname(name)
        return None

    return redirect
