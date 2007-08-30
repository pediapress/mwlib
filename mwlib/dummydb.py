
# Copyright (c) 2007, pediapress GMBH
# See README.txt for additional licensing information.

class DummyDB(object):
    def getRawArticle(self, name):
        return None

    def getTemplate(self, name, followRedirects=False):
        return None
