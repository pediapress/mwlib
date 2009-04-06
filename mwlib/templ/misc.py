
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.txt for additional licensing information.

from mwlib.templ import evaluate

class DictDB(object):
    """wikidb implementation used for testing"""
    def __init__(self, *args, **kw):
        if args:
            self.d, = args
        else:
            self.d = {}
        
        self.d.update(kw)

        normd = {}
        for k, v in self.d.items():
            normd[k.lower()] = v
        self.d = normd
        
    def getRawArticle(self, title, revision=None):
        return self.d[title.lower()]

    def getTemplate(self, title, dummy):
        return self.d.get(title.lower(), u"")
    
def expandstr(s, expected=None, wikidb=None, pagename='thispage'):
    """debug function. expand templates in string s"""
    if wikidb:
        db = wikidb
    else:
        db = DictDB(dict(a=s))

    te = evaluate.Expander(s, pagename=pagename, wikidb=db)
    res = te.expandTemplates()
    print "EXPAND: %r -> %r" % (s, res)
    if expected is not None:
        assert res==expected, "expected %r, got %r" % (expected, res)
    return res
