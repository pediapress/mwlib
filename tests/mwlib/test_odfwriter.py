#! /usr/bin/env py.test
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

import os
import re
import sys
import tempfile
from contextlib import suppress
from io import StringIO

import py
import pytest

import mwlib.parser
from mwlib.parser import advtree
from mwlib.parser.dummydb import DummyDB
from mwlib.parser.refine.uparser import parse_string
from mwlib.writers.odf.writer import ODFWriter, preprocess

ODFWriter.ignoreUnknownNodes = False

# hook for reuse of generated files


def remove_file(fn):
    os.remove(fn)


odtfile_cb = remove_file

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
        with suppress(SystemExit), open(exe.strpath, "rb") as file:
            exec(compile(file.read(), exe.strpath, "exec"), odflint.__dict__)
        return odflint
    finally:
        sys.argv[:] = argv
        sys.stderr = stderr


odflint = _get_odflint_module()


def lint_file(path):
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
    """THIS USES odflint AND WILL FAIL IF NOT INSTALLED."""
    fh, tfn = tempfile.mkstemp()
    odfw.getDoc().save(tfn, True)
    tfn += ".odt"
    r = lint_file(tfn)
    # FIXME: odflint currently raises an error for mimetype - maybe a bug? This is the error:
    # "Error: The 'mimetype' member must not have extra header info\n"
    if len(r) and "mimetype" not in r:
        raise ValidationError(r)
    odtfile_cb(tfn)


def get_xml(wikitext):
    db = DummyDB()
    r = parse_string(title="test", raw=wikitext, wikidb=db)
    advtree.build_advanced_tree(r)
    preprocess(r)
    mwlib.parser.show(sys.stdout, r)
    odfw = ODFWriter()
    odfw.writeTest(r)
    validate(odfw)
    xml = odfw.asstring()
    print(xml)  # useful to inspect generated xml
    return xml


def test_pass():
    raw = """
== Hello World ==
kthxybye
"""
    xml = get_xml(raw)
    assert "Hello World" in xml


def test_fix_paragraphs():
    raw = """
<p>
<ul><li>a</li></ul>
</p>
"""
    xml = get_xml(raw)
    assert "<text:list-item>" in xml
    assert '<text:p text:style-name="TextBody">a</text:p>' in xml


def test_gallery():
    raw = """
<gallery>
Image:Wikipedesketch1.png|The Wikipede
Image:Wikipedesketch1.png|A Wikipede
Image:Wikipedesketch1.png|Wikipede working
Image:Wikipedesketch1.png|Wikipede's Habitat
Image:Wikipedesketch1.png|A mascot for Wikipedia
Image:Wikipedesketch1.png|One logo for Wikipedia
Image:Wikipedesketch1.png|Wikipedia has bugs
Image:Wikipedesketch1.png|The mascot of Wikipedia
</gallery>"""
    xml = get_xml(raw)
    assert "Wikipedia" in xml


raw = r"""<b class="test">bold</b>
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
th<!-- this is comment -->is includes a comment"""


@pytest.mark.parametrize("x", raw.split("\n"))
def test_validate_tags(x):
    """
    this test checks only basic XHTML validation
    """
    res = get_xml(x)
    assert "<office:text" in res


def test_sections():
    raw = """
== Section 1 ==

text with newline above

more text with newline, this will result in paragrahps

=== This should be a sub section ===
currently the parser ends sections at paragraphs.
unless this bug is fixed subsections are not working

==== subsub section ====
this test will validate, but sections will be broken.

"""
    xml = get_xml(raw)

    reg = re.compile(r'text:outline-level="(\d)"', re.MULTILINE)
    res = list(reg.findall(xml))
    goal = ["1", "2", "3", "4"]
    if res != goal:
        print(f"{res} should be {goal}")
        print(xml)
    assert res == goal


def test_invalid_level_sections():
    raw = """

= 1 =
== 2 ==
=== 3 ===
==== 4 ====
===== 5 =====
====== 6 ======
======= 7 =======
======== 8 ========
text
"""
    xml = get_xml(raw)

    reg = re.compile(r'text:outline-level="(\d)"', re.MULTILINE)
    res = list(reg.findall(xml))
    # article title is on the first level, therefore we have "6"*4
    goal = ["1", "2", "3", "4", "5", "6", "6", "6", "6"]
    if res != goal:
        print(f"{res} should be {goal}")
        print(xml)
    assert res == goal


def disabled_test_empty_sections():
    # decision to show empty sections
    raw = """=  =
= correct =
== with title no children ==""".decode(
        "utf8"
    )
    xml = get_xml(raw)
    reg = re.compile(r'text:name="(.*?)"', re.MULTILINE)
    res = list(reg.findall(xml))
    goal = ["test", "correct "]  # article title is on the first level,
    if res != goal:
        print(f"{res} should be {goal}")
        print(xml)
    assert res == goal


def test_newlines():
    raw = """== Rest of the page ==

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
"""
    xml = get_xml(raw)
    assert "Rest of the page" in xml


def test_bold():
    raw = """
is this '''bold'''

another '''bold''

"""
    xml = get_xml(raw)
    assert "bold" in xml


def test_ulists():
    raw = """== Rest of the page ==

* Unordered Lists are easy to do:
** start every line with a star,
*** more stars means deeper levels.
* A newline
* in a list
marks the end of the list.
* Of course,
* you can
* start again.
"""
    xml = get_xml(raw)
    assert "Unordered Lists" in xml


def test_olists():
    raw = """== Rest of the page ==


# Numbered lists are also good
## very organized
## easy to follow
# A newline
# in a list
marks the end of the list.
# New numbering starts
# with 1.

"""
    xml = get_xml(raw)
    assert "very organized" in xml


def test_mixed_lists():
    raw = """== Rest of the page ==

* You can even do mixed lists
*# and nest them
*#* or break lines<br />in lists

"""
    xml = get_xml(raw)
    assert "mixed lists" in xml


def test_definition_lists():
    raw = """== Rest of the page ==
; word : definition of the word
; longer phrase
: phrase defined


"""
    xml = get_xml(raw)
    assert "definition of the word" in xml


def test_preprocess():
    raw = """== Rest of the page ==

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

"""
    xml = get_xml(raw)
    assert "very organized" in xml


def test_paragraphs_in_sections():
    raw = """== section 1 ==
s1 paragraph 1

s1 paragraph 2

=== subsection ===
sub1 paragraph 1

sub1 paragraph 1

== section 2 ==
s2 paragraph 1

s2 paragraph 2

"""
    xml = get_xml(raw)
    assert "section 2" in xml


def test_math():
    raw = r"""
<math> Q = \begin{bmatrix} 1 & 0 & 0 \\ 0 & \frac{\sqrt{3}}{2} & \frac12 \\ 0 & -\frac12 & \frac{\sqrt{3}}{2} \end{bmatrix} </math>
"""
    xml = get_xml(raw)
    assert "test" in xml


def test_math2():
    raw = r"""<math>\exp(-\gamma x)</math>"""
    xml = get_xml(raw)
    assert "test" in xml


@pytest.mark.xfail
def test_snippets(snippet):
    print("testing", repr(s.txt))
    xml = get_xml(s.txt)
    assert "test" in xml


def test_horizontal_rule():
    raw = r"""before_hr<hr/>after_hr"""
    xml = get_xml(raw)
    assert "before_hr" in xml


def test_tables():
    raw = r"""
{| border="1" cellspacing="0" cellpadding="5" align="center"
! This
! is
|-
| a
| cheese
|-
|}
"""
    xml = get_xml(raw)
    assert "cheese" in xml


def test_colspan():
    raw = r"""
<table>
<tr><td>a</td><td>b</td></tr>
<tr><td colspan="2">ab</td></tr>
</table>
"""
    xml = get_xml(raw)
    assert "ab" in xml


def test_definition_description():
    # works with a hack
    raw = r"""
: a
:* b
"""
    xml = get_xml(raw)
    assert "a" in xml
    assert "b" in xml


def test_italic():
    # DOES NOT WORK FOR ME in OpenOffice
    raw = r"""
=== a===
B (''Molothrus ater'') are


"""
    xml = get_xml(raw)
    print(xml)
    assert "Molothrus" in xml
