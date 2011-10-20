# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

"""custom json encoder/decoder, which can handle metabook objects"""

from mwlib import metabook

try:
    import json
    from json import loads # protect us against http://pypi.python.org/pypi/python-json/
except ImportError:
    import simplejson as json


def object_hook(dct):
    try:
        type = dct["type"]
    except KeyError:
        type = None
        
    if type in ["collection", "article", "chapter", "source", "interwiki",  "license",  "wikiconf", "custom"]:
        klass = getattr(metabook, type)
        d = {}
        for k, v in dct.items():
            d[str(k)] = v
        d["type"] = type
        return klass(**d)
        
    return dct

class mbencoder(json.JSONEncoder):
    def default(self, obj):
        try:
            m = obj._json
        except AttributeError:
            return json.JSONEncoder.default(self, obj)
        
        return m()

def loads(data):
    return json.loads(data, object_hook=object_hook)

def dump(obj, fp, **kw):
    return json.dump(obj, fp, cls=mbencoder, **kw)

def dumps(obj, **kw):
    return json.dumps(obj, cls=mbencoder, **kw)

def load(fp):
    return json.load(fp, object_hook=object_hook)
