#! /usr/bin/env py.test
# -*- coding: utf-8 -*-
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.txt for additional licensing information.
import sys
from mwlib.dummydb import DummyDB
from mwlib.uparser import parseString
from mwlib.parser import show
from mwlib.docbookwriter import DocBookWriter, preprocess
from mwlib.xhtmlwriter import validate as mwvalidate
from mwlib.xfail import xfail

DocBookWriter.ignoreUnknownNodes = False

def getXML(wikitext):
    db = DummyDB()
    r = parseString(title="test", raw=wikitext, wikidb=db)
    print "before preprocess"
    show(sys.stdout, r)
    preprocess(r)
    print "after preprocess"
    show(sys.stdout, r)
    dbw = DocBookWriter()
    dbw.dbwriteArticle(r)
    return dbw.asstring()


class ValidationError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)
 
def validate(xml):
    "THIS USES xmllint AND WILL FAIL IF NOT INSTALLED"
    r = mwvalidate(xml)
    if len(r):
        print xml
        print "error:"
        print r
        raise ValidationError(r)


@xfail
def test_pass():
    raw = """
== Hello World ==
kthxybye
""".decode("utf8")
    xml = getXML(raw)
    validate(xml)

@xfail
def test_fixparagraphs(): 
    raw = """
<p>
<ul><li>a</li></ul>
</p>
""".decode("utf8")
    xml = getXML(raw)
    validate(xml)
    




@xfail
def test_gallery():
    """http://code.pediapress.com/wiki/ticket/219"""
    raw="""
<gallery>
Image:Wikipedesketch1.png|The Wikipede
Image:Wikipedesketch1.png|A Wikipede
Image:Wikipedesketch1.png|Wikipede working
Image:Wikipedesketch1.png|Wikipede's Habitat 
Image:Wikipedesketch1.png|A mascot for Wikipedia
Image:Wikipedesketch1.png|One logo for Wikipedia
Image:Wikipedesketch1.png|Wikipedia has bugs
Image:Wikipedesketch1.png|The mascot of Wikipedia
</gallery>""".decode("utf8")
    xml = getXML(raw)
    validate(xml)




@xfail
def test_sections():
    raw='''
== Section 1 ==

text with newline above

more text with newline, this will result in paragrahps

=== This should be a sub section ===
currently the parser ends sections at paragraphs. 
unless this bug is fixed subsections are not working

==== subsub section ====
this test will validate, but sections will be broken.

'''.decode("utf8")
    xml = getXML(raw)
    validate(xml)
    

def test_newlines():
    raw='''== Rest of the page ==

A single
newline
has no
effect on the
layout.

<h1>heading 1</h1>

But an empty line
starts a new paragraph.

You can break lines<br />
without starting a new paragraph.
'''.decode("utf8")
    xml = getXML(raw)

    


def test_ulists():
    raw='''== Rest of the page ==

* Unordered Lists are easy to do:
** start every line with a star,
*** more stars means deeper levels.
* A newline
* in a list  
marks the end of the list.
* Of course,
* you can
* start again.
'''.decode("utf8")
    xml = getXML(raw)

    


def test_olists():
    raw='''== Rest of the page ==


# Numbered lists are also good
## very organized
## easy to follow
# A newline
# in a list  
marks the end of the list.
# New numbering starts
# with 1.

'''.decode("utf8")
    xml = getXML(raw)


def test_mixedlists():
    raw='''== Rest of the page ==

* You can even do mixed lists
*# and nest them
*#* or break lines<br />in lists

'''.decode("utf8")
    xml = getXML(raw)

def test_definitionlists():
    raw='''== Rest of the page ==
; word : definition of the word
; longer phrase 
: phrase defined


'''.decode("utf8")
    xml = getXML(raw)

def test_preprocess():
    raw='''== Rest of the page ==

A single
newline
has no
effect on the
layout.

<h1>heading 1</h1>

But an empty line
starts a new paragraph.

You can break lines<br />
without starting a new paragraph.

* Unordered Lists are easy to do:
** start every line with a star,
*** more stars means deeper levels.
* A newline
* in a list  
marks the end of the list.
* Of course,
* you can
* start again.


# Numbered lists are also good
## very organized
## easy to follow
# A newline
# in a list  
marks the end of the list.
# New numbering starts
# with 1.

* You can even do mixed lists
*# and nest them
*#* or break lines<br />in lists

'''.decode("utf8")
    xml = getXML(raw)

def test_paragraphsinsections():
    raw='''== section 1 ==
s1 paragraph 1

s1 paragraph 2

=== subsection ===
sub1 paragraph 1

sub1 paragraph 1

== section 2 ==
s2 paragraph 1

s2 paragraph 2

'''.decode("utf8")
    xml = getXML(raw)


def test_math():
    raw=r'''
<math> Q = \begin{bmatrix} 1 & 0 & 0 \\ 0 & \frac{\sqrt{3}}{2} & \frac12 \\ 0 & -\frac12 & \frac{\sqrt{3}}{2} \end{bmatrix} </math>
'''.decode("utf8")
    xml = getXML(raw)


def test_math2():
    raw=r'''<math>\exp(-\gamma x)</math>'''
    xml = getXML(raw)

def test_snippets():
    from mwlib import snippets
    for s in snippets.get_all():
        print "testing", repr(s.txt)
        xml = getXML(s.txt)


@xfail
def test_heiko():
    raw = '''
[[User:Heiko/Editing]]

[[User:Heiko/Size in Volumes]] vanished
'''
    xml = getXML(raw)
    assert "Heiko/Editing" in xml
