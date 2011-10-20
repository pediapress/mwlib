
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

from mwlib.siteinfo import get_siteinfo
from mwlib.templ import evaluate

class page(object):
    def __init__(self, rawtext):
        self.rawtext = rawtext
        
                 
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
            normd[k.lower().replace(" ",  "_")] = v
        self.d = normd

        self.siteinfo = get_siteinfo('de')

    def normalize_and_get_page(self, title, defaultns=0):
        return page(self.d.get(title.lower().replace(" ", "_"), u""))
        
    def get_siteinfo(self):
        return self.siteinfo


    
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
