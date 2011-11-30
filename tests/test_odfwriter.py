#! /usr/bin/env py.test
# -*- coding: utf-8 -*-
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

import os, sys, re, tempfile
from StringIO import StringIO
import py

from mwlib.dummydb import DummyDB
from mwlib.uparser import parseString
from mwlib import advtree
import mwlib.parser
from mwlib.odfwriter import ODFWriter, preprocess

ODFWriter.ignoreUnknownNodes = False

# hook for reuse of generated files
def removefile(fn):
    os.remove(fn)
odtfile_cb = removefile

# read the odflint script as module.
# calling this in process speeds up the tests considerably.

def _get_odflint_module():
    exe = py.path.local.sysfind("odflint")
    assert exe is not None, "odflint not found"

    argv = sys.argv[:]
    stderr = sys.stderr
    odflint = sys.__class__("odflint")

    try:
        sys.stderr = StringIO()
        del sys.argv[1:]
        try:
            execfile(exe.strpath, odflint.__dict__)
        except SystemExit:
            pass
        return odflint
    finally:
        sys.argv[:] = argv
        sys.stderr = stderr

odflint = _get_odflint_module()

def lintfile(path):
    stdout, stderr = sys.stdout, sys.stderr
    try:
        sys.stdout = sys.stderr = StringIO()
        odflint.lint(path)
        return sys.stdout.getvalue()
    finally:
        sys.stdout = stdout
        sys.stderr = stderr


class ValidationError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)


 
def validate(odfw):
    "THIS USES odflint AND WILL FAIL IF NOT INSTALLED"
    fh, tfn = tempfile.mkstemp() 
    odfw.getDoc().save(tfn, True)
    tfn +=".odt"
    r = lintfile(tfn)
    if len(r):
        raise ValidationError, r
    odtfile_cb(tfn)


def getXML(wikitext):
    db = DummyDB()
    r = parseString(title="test", raw=wikitext, wikidb=db)
    advtree.buildAdvancedTree(r)
    preprocess(r)
    mwlib.parser.show(sys.stdout, r)
    odfw = ODFWriter()
    odfw.writeTest(r)
    validate(odfw)
    xml = odfw.asstring()
    #print xml # usefull to inspect generateded xml
    return xml



def test_pass():
    raw = """
== Hello World ==
kthxybye
""".decode("utf8")
    xml = getXML(raw)

def test_fixparagraphs(): 
    raw = """
<p>
<ul><li>a</li></ul>
</p>
""".decode("utf8")
    xml = getXML(raw)


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
    xml = getXML(raw)

    

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

    for x in raw.split("\n"):
        yield getXML, x


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
    
    reg = re.compile(r'text:outline-level="(\d)"', re.MULTILINE)
    res =  list(reg.findall(xml))
    goal =  [u'1', u'2', u'3', u'4']
    print res, "should be",goal
    if not res == goal:
        print xml
        assert res == goal



def test_invalid_level_sections():
    raw='''

= 1 =
== 2 ==
=== 3 ===
==== 4 ====
===== 5 =====
====== 6 ======
======= 7 =======
======== 8 ========
text
'''.decode("utf8")
    xml = getXML(raw)
    
    reg = re.compile(r'text:outline-level="(\d)"', re.MULTILINE)
    res =  list(reg.findall(xml))
    goal =  ['1', '2', '3', '4', '5', '6', '6', '6', '6'] # article title is on the first level, therefore we have "6"*4
    print res, "should be",goal
    if not res == goal:
        print xml
        assert res == goal


def disabled_test_empty_sections():
    # decision to show empty sections
    raw='''=  =
= correct =
== with title no children =='''.decode("utf8")
    xml = getXML(raw)
    reg = re.compile(r'text:name="(.*?)"', re.MULTILINE)
    res =  list(reg.findall(xml))
    goal =  [u'test', 'correct '] # article title is on the first level, 
    print res, "should be",goal
    if not res == goal:
        print xml
        assert res == goal



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


def test_bold():
    raw="""
is this '''bold''' 

another '''bold''

""".decode("utf8")
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

def test_horizontalrule():
    raw=r'''before_hr<hr/>after_hr'''
    xml = getXML(raw)




def test_tables():
    raw = r'''
{| border="1" cellspacing="0" cellpadding="5" align="center"
! This
! is
|- 
| a
| cheese
|-
|}
'''
    xml = getXML(raw)
    assert "cheese" in xml


def test_colspan():
    raw = r'''
<table>
<tr><td>a</td><td>b</td></tr>
<tr><td colspan="2">ab</td></tr>
</table>
'''
    xml = getXML(raw)



def test_definitiondescription():
    # works with a hack
    raw = r'''
: a
:* b
'''
    xml = getXML(raw)


def test_italic():
    # DOES NOT WORK FOR ME in OpenOffice
    raw= r'''
=== a===
B (''Molothrus ater'') are


'''
    xml = getXML(raw)
    print xml
    assert "Molothrus" in xml

