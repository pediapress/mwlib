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

def test_birth_date_and_age():
    db = DictDB({
            "birth date and age": '[[{{MONTHNAME|{{{2|{{{month|{{{2}}}}}}}}}}} {{{3|{{{day|{{{3}}}}}}}}}]] [[{{{1|{{{year|{{{1}}}}}}}}}]]<font class="noprint"> (age&nbsp;{{age | {{{1|{{{year|{{{1}}}}}}}}} | {{{2|{{{month|{{{2}}}}}}}}} | {{{3|{{{day|{{{3}}}}}}}}} }})</font>',
            
            "age" : '<includeonly>{{#expr:({{{4|{{CURRENTYEAR}}}}})-({{{1}}})-(({{{5|{{CURRENTMONTH}}}}})<({{{2}}})or({{{5|{{CURRENTMONTH}}}}})=({{{2}}})and({{{6|{{CURRENTDAY}}}}})<({{{3}}}))}}</includeonly>',
            'a': '{{birth date and age|1960|02|8}}'
            })
    te = expander.Expander(db.getRawArticle("a"), pagename="thispage", wikidb=db)
    res = te.expandTemplates()
    print "EXPANDED:", repr(res)
    import datetime
    now=datetime.datetime.now()
    b=datetime.datetime(1960,2,8)
    age = now.year-b.year
    if now.month*32+now.day < b.month*32+b.day:
        age -= 1
    
    expected = u"age&nbsp;%s" % age
    assert expected in res

    assert u"February" in res
    
def test_five():
    txt = "text of the tnext template"
    db=DictDB(dict(
            a="{{t1|tnext}}",
            t1="{{{{{1}}}}}",
            tnext=txt))
    te = expander.Expander(db.getRawArticle("a"), pagename="thispage", wikidb=db)
    res = te.expandTemplates()
    print "EXPANDED:", repr(res)
    assert res==txt

def test_five_parser():
    n=expander.parse("{{{{{1}}}}}")
    expander.show(n)
    assert isinstance(n, expander.Template)

def test_five_parser():
    n=expander.parse("{{{{{1}}}}}")
    n.show()
    assert isinstance(n, expander.Template)

def test_five_two_three():
    n=expander.parse("{{{{{1}} }}}")
    n.show()
    assert isinstance(n, expander.Variable)

def test_five_three_two():
    n=expander.parse("{{{{{1}}} }}")
    n.show()
    assert isinstance(n, expander.Template)

    
