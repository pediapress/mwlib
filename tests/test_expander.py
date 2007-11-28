#! /usr/bin/env py.test

from mwlib import expander

class DictDB(object):
    def __init__(self, d):
        self.d = d

    def getRawArticle(self, title):
        return self.d[title]

    def getTemplate(self, title, dummy):
        return self.d.get(title, u"")



def test_noexpansion_inside_pre():
    db = DictDB(dict(Art="<pre>A{{Pipe}}B</pre>",
                     Pipe="C"))

    te = expander.Expander(db.getRawArticle("Art"), pagename="thispage", wikidb=db)
    res = te.expandTemplates()

    
    print "EXPANDED:", repr(res)
    assert u"ACB" not in res
    assert u"A{{Pipe}}B" in res


def test_undefined_variable():
    db = DictDB(dict(Art="{{Pipe}}",
                     Pipe="{{{undefined_variable}}}"))
    
    te = expander.Expander(db.getRawArticle("Art"), pagename="thispage", wikidb=db)
    res = te.expandTemplates()
    print "EXPANDED:", repr(res)
    assert u"{{{undefined_variable}}}" in res, "wrong expansion for undefined variable"
