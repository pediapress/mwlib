
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

import os

try:
    import simplejson as json
except ImportError:
    import json

_cache = {}

def _get_path(lang):
    return os.path.join(os.path.dirname(__file__), "siteinfo-%s.json" % lang)
    
def get_siteinfo(lang):
    try:
        return _cache[lang]
    except KeyError:
        pass

    si = None
    p = _get_path(lang)
    if os.path.exists(p):
        si = json.load(open(p, "rb"))

    _cache[lang] = si
    return si

# def get_available_languages():
#     import glob
#     glob.glob(_get_path("*"))
