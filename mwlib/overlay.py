
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.txt for additional licensing information.

import os
from mwlib import namespace

                 
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

        self.docs = {}
        
        for block in unicode(open(fn, "rb").read(), 'utf-8').split(" "):
            if not block:
                continue
            title, txt = block.split("\n", 1)

            ns, partial, full = namespace.splitname(title)
            self.docs[(ns, partial)] = txt

    
    def getTemplate(self, title, followRedirects=True):
        ns, partial, full = namespace.splitname(title, defaultns=namespace.NS_TEMPLATE)
        try:
            return self.docs[(ns, partial)]
        except KeyError:
            pass
        return self.db.getTemplate(title, followRedirects=followRedirects)
    
    def getRawArticle(self, title, revision=None):
        ns, partial, full = namespace.splitname(title)
        try:
            return self.docs[(ns, partial)]
        except KeyError:
            pass
        return self.db.getRawArticle(title, revision=revision)
    
    def __getattr__(self, name):
        return getattr(self.db, name)
