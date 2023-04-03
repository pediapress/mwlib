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

    si = None
    p = _get_path(lang)
    if p.exists():
        with p.open("r", encoding="utf-8") as f:
            si = json.load(f)

    _cache[lang] = si
    return si
