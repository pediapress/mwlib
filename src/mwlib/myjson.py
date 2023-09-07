# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

"""custom json encoder/decoder, which can handle metabook objects"""

from mwlib import metabook

try:
    import simplejson as json
except ImportError:
    import json


def object_hook(dct):
    try:
        document_type = dct["type"]
    except KeyError:
        document_type = None

    if document_type in [
        "collection",
        "article",
        "Chapter",
        "source",
        "interwiki",
        "License",
        "WikiConf",
        "custom",
    ]:
        klass = getattr(metabook, document_type)
        d = {}
        for k, v in dct.items():
            d[str(k)] = v
        d["type"] = document_type
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
    return json.dump(obj, fp, ensure_ascii=False, cls=mbencoder, **kw)


def dumps(obj, **kw):
    return json.dumps(obj, cls=mbencoder, **kw)


def load(fp):
    return json.load(fp, object_hook=object_hook)
