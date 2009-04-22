
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.txt for additional licensing information.

import os
# import glob

try:
    import json
except ImportError:
    import simplejson as json

_cache = {}

def get_siteinfo(lang):
    try:
        return _cache[lang]
    except KeyError:
        pass

    si = None
    p = os.path.join(os.path.dirname(__file__), "siteinfo-%s.json" % lang)
    if os.path.exists(p):
        si = json.load(open(p, "rb"))

    _cache[lang] = si
    return si
    

    
