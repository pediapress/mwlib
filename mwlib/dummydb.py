
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.txt for additional licensing information.

class DummyDB(object):
    def getURL(self, title, revision=None):
        return None

    def get_siteinfo(self):
        from mwlib import siteinfo
        return siteinfo.get_siteinfo("en")
    
