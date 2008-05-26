#! /usr/bin/env py.test
# -*- coding: utf-8 -*-
# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.
from mwlib.dummydb import DummyDB
from mwlib.uparser import parseString
import mwlib.advtree
from mwlib.xhtmlwriter import MWXHTMLWriter

import subprocess
import StringIO
import tempfile
import os

def getXHTML(wikitext):
    db = DummyDB()
    r = parseString(title="test", raw=wikitext, wikidb=db)
    mwlib.advtree.buildAdvancedTree(r)
    dbw = MWXHTMLWriter()
    dbw.write(r)
    return dbw.asstring()

class ValidationError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)
 
def validate(xhtml):
    "THIS USES xmllint AND WILL FAIL IF NOT INSTALLED"
    fh, tfn = tempfile.mkstemp()
    open(tfn, "w").write(xhtml)
    cmd = "xmllint --noout --valid %s" %tfn
    p =subprocess.Popen(cmd, shell=True,stderr=subprocess.PIPE, close_fds=True)
    p.wait()
    r = p.stderr.read()
    os.remove(tfn)
    if len(r):
        print xhtml
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
    validate(xhtml)
    

