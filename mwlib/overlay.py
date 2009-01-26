
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.txt for additional licensing information.

import os

                 
class OverlayDB(object):
    def __init__(self, db, basedir):
        self.db = db
        self.basedir = basedir
        
    def getRawArticle(self, title, revision=None):
        p = os.path.join(self.basedir, title)
        if os.path.isfile(p):
            return unicode(open(p, 'rb').read(), 'utf-8')
        return self.db.getRawArticle(title)

    def getTemplate(self, title, followRedirects=False):
        p = os.path.join(self.basedir, title)
        if os.path.isfile(p):
            return unicode(open(p, 'rb').read(), 'utf-8')
        return self.db.getTemplate(title, followRedirects=followRedirects)

    def __getattr__(self, name):
        return getattr(self.db, name)


class FlatDB(OverlayDB):
    def __init__(self, db, fn):
        self.fn = fn
        self.db = db
        self.articles = {}
        self.templates = {}
        
        
        for block in unicode(open(fn, "rb").read(), 'utf-8').split(" "):
            if not block:
                continue
            title, txt = block.split("\n", 1)
            if title.startswith("Template:"):
                title = title[len("Template:"):]
                self.templates[title] = txt
            elif title.startswith("Article:"):
                title = title[len("Article:"):]
                self.articles[title] = txt
            else:
                assert 0, "bad title"

    def getTemplate(self, title, followRedirects=True):
        try:
            return self.templates[title]
        except KeyError:
            pass
        return self.db.getTemplate(title, followRedirects=followRedirects)
    
    def getRawArticle(self, title, revision=None):
        try:
            return self.articles[title]
        except KeyError:
            pass
        return self.db.getRawArticle(title, revision=revision)
    
    def __getattr__(self, name):
        return getattr(self.db, name)
