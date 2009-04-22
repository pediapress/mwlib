
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.txt for additional licensing information.

import os
# import glob

try:
    import json
except ImportError:
    import simplejson as json

def get_siteinfo(lang):
    p = os.path.join(os.path.dirname(__file__), "siteinfo-%s.json" % lang)
    if os.path.exists(p):
        si = json.load(open(p, "rb"))
        return si
    
    return None

    

    
