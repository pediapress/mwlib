#! /usr/bin/env python

# Copyright (c) 2007, pediapress GMBH
# See README.txt for additional licensing information.

import os
import zipfile
import simplejson
import tempfile

class Wiki(object):
    def __init__(self, path):
        self.zf = zipfile.ZipFile(path)
        c = simplejson.loads(self.zf.read("contents.json"))
        self.articles = c['articles']
        self.templates = c['templates']

    def getRawArticle(self, name):
        return self.articles[name]

    def getTemplate(self, name, followRedirects=True):
        return self.templates[name]

class ImageDB(object):
    def __init__(self, path):
        self.zf = zipfile.ZipFile(path)
        self._tmpdir = None

    @property
    def tmpdir(self):
        if self._tmpdir is None:
            self._tmpdir = unicode(tempfile.mkdtemp())

        return self._tmpdir

    def getDiskPath(self, name):
        try:
            data = self.zf.read((u"images/%s" % name).encode("utf-8"))
        except KeyError: # no such file
            return None

        res = os.path.join(self.tmpdir, name)
        f=open(res, "wb")
        f.write(data)
        f.close()
        return res


