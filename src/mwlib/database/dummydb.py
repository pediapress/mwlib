# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.
from mwlib import siteinfo


class DummyDB:
    def __init__(self, lang="en"):

        self.siteinfo = siteinfo.get_siteinfo(lang)

    def get_url(self, title, _=None):
        return None

    def get_siteinfo(self):
        return self.siteinfo
