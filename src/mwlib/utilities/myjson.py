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
        document_type = dct["type"].lower()
    except KeyError:
        document_type = None
    class_name_mapping = {
        "collection": "collection",
        "article": "article",
        "chapter": "Chapter",
        "source": "Source",
        "interwiki": "Interwiki",
        "license": "License",
        "wikiconf": "WikiConf",
        "custom": "custom",
    }
    if document_type in class_name_mapping:
        klass = getattr(metabook, class_name_mapping[document_type])
        sanitized_dict = {}
        for k, value in dct.items():
            sanitized_dict[str(k)] = value
        sanitized_dict["type"] = document_type
        return klass(**sanitized_dict)
    print("no match", document_type)
    return dct


class MbEncoder(json.JSONEncoder):
    def default(self, obj):
        try:
            json_method = obj._json
        except AttributeError:
            return json.JSONEncoder.default(self, obj)

        return json_method()


def loads(data):
    return json.loads(data, object_hook=object_hook)


def dump(obj, file_path, **kw):
    return json.dump(obj, file_path, ensure_ascii=False, cls=MbEncoder, **kw)


def dumps(obj, **kw):
    return json.dumps(obj, cls=MbEncoder, **kw)


def load(file_path):
    return json.load(file_path, object_hook=object_hook)
