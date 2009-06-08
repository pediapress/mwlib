#! /usr/bin/env py.test
# -*- coding: utf-8 -*-
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.txt for additional licensing information.
import sys
from mwlib.dummydb import DummyDB
from mwlib.uparser import parseString
from mwlib.parser import show
from mwlib.xhtmlwriter import MWXHTMLWriter, preprocess
from mwlib.xhtmlwriter import validate as mwvalidate
from mwlib.xfail import xfail
import re

MWXHTMLWriter.ignoreUnknownNodes = False

def getXHTML(wikitext):
    db = DummyDB()
    r = parseString(title="test", raw=wikitext, wikidb=db)
    preprocess(r)
    show(sys.stdout, r)
    dbw = MWXHTMLWriter()
    dbw.writeBook(r)
    return dbw.asstring()


class ValidationError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)


def validate(xml):
    r = mwvalidate(xml)
    if len(r):
        print xml
        raise ValidationError, r


def test_pass():
    raw = """
== Hello World ==
kthxybye
""".decode("utf8")
    xhtml = getXHTML(raw)
    validate(xhtml)

def test_fixparagraphs(): 
    raw = """
<p>
<ul><li>a</li></ul>
</p>
""".decode("utf8")
    xhtml = getXHTML(raw)
    validate(xhtml)
    


def test_gallery():
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
    xhtml = getXHTML(raw)
    validate(xhtml)

def test_math():
    raw=r'''
<math> Q = \begin{bmatrix} 1 & 0 & 0 \\ 0 & \frac{\sqrt{3}}{2} & \frac12 \\ 0 & -\frac12 & \frac{\sqrt{3}}{2} \end{bmatrix} </math>
'''.decode("utf8")
    xhtml = getXHTML(raw)
    #validate(xhtml) # this does not validate as long as we use XHTML1.0
    
    
    

def test_validatetags():
    """
    this test checks only basic XHTML validation 
    """
    raw=r'''<b class="test">bold</b>
<big>big</big>
<blockquote>blockquote</blockquote>
break after <br/> and before this
<table class="testi vlist"><caption>caption for the table</caption><thead><th>heading</th></thead><tbody><tr><td>cell</td></tr></tbody></table>
<center>center</center>
<cite>cite</cite>
<code>code</code>
<source class="test_class" id="test_id">source</source>
<dl><dt>dt</dt><dd>dd</dd></dl>
<del>deleted</del>
<div>division</div>
<em>em</em>
<font>font</font>
<h1>h1</h1>
<h6>h6</h6>
<hr/>
<i>i</i>
<ins>ins</ins>
<ol><li>li 1</li><li>li 2</li></ol>
<ul><li>li 1</li><li>li 2</li></ul>
<p>paragraph</p>
<pre>preformatted</pre>
<ruby><rb>A</rb><rp>(</rp><rt>aaa</rt><rp>)</rp></ruby>
<s>s</s>
<small>small</small>
<span>span</span>
<strike>strke</strike>
<strong>strong</strong>
<sub>sub</sub>
<sup>sup</sup>
<tt>teletyped</tt>
<u>u</u>
<var>var</var>
th<!-- this is comment -->is includes a comment'''.decode("utf8")

    def get_xhtml_and_validate(txt):
        xhtml = getXHTML(x)
        validate(xhtml)
        
    for x in raw.split("\n"):
        yield get_xhtml_and_validate, x

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
    xhtml = getXHTML(raw)
    validate(xhtml)
    
    reg = re.compile(r"<(h\d)", re.MULTILINE)
    res =  list(reg.findall(xhtml))
    expect = ['h1', 'h2', 'h3', 'h4']
    print res, "should be", expect
    if not res == expect:
        print xhtml
        assert res == expect

@xfail
def test_snippets():
    """http://code.pediapress.com/wiki/ticket/220"""
    from mwlib import snippets
    for s in snippets.get_all():
        print "testing", repr(s.txt)
        xhtml = getXHTML(s.txt)
        validate(xhtml)
        
