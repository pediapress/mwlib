
# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.

import os

class OverlayDB(object):
    def __init__(self, db, basedir):
        self.db = db
        self.basedir = basedir

    def getRawArticle(self, title):
        p = os.path.join(self.basedir, title)
        if os.path.isfile(p):
            return unicode(open(p, 'rb').read(), 'utf-8')
        return self.db.getRawArticle(title)

    def getTemplate(self, title, followRedirects=False):
        p = os.path.join(self.basedir, title)
        if os.path.isfile(p):
            return unicode(open(p, 'rb').read(), 'utf-8')
        return self.db.getTemplate(title, followRedirects=followRedirects)
