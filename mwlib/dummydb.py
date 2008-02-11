
# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.

class DummyDB(object):
    def getRawArticle(self, name):
        return None

    def getTemplate(self, name, followRedirects=False):
        return None
