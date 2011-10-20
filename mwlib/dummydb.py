
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

class DummyDB(object):
    def __init__(self, lang="en"):
        from mwlib import siteinfo
        self.siteinfo = siteinfo.get_siteinfo(lang)

    def getURL(self, title, revision=None):
        return None

    def get_siteinfo(self):
        return self.siteinfo
