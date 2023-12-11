# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

import json
from pathlib import Path

_cache = {}


def _get_path(lang):
    return Path(__file__).parent / f"siteinfo-{lang}.json"


def get_siteinfo(lang):
    try:
        return _cache[lang]
    except KeyError:
        pass

    site_info = None
    path = _get_path(lang)
    if path.exists():
        with path.open("r", encoding="utf-8") as site_info_file:
            site_info = json.load(site_info_file)

    _cache[lang] = site_info
    return site_info
