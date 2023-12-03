#! /usr/bin/env py.test
# -*- coding: utf-8 -*-

# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.

from renderhelper import renderMW

t = u'Some sample text with funky chars. Umlauts: äöü ÄÖÜ some symbols: @ € ~ # ^ § '

def test_paragraph():

    txt = t*20
    txt = '\n\n'.join([txt]*5)
    renderMW(txt, 'paragraph')

def test_intraWikiLinks():
    txt = u'Intra wiki link: [[Articlename]] with different link text: [[Other Article|Some funky text]]'
    renderMW(txt, 'intrawikilinks')
    
def test_externalLink():
    txt = u'External link to [http://example.com] with optional link text [http://example.com bla blub]'
    renderMW(txt, 'externallink')

def test_url():
    txt = u"some url: http://example.com. now a url with umlauts: http://dasörtliche.de and now a italic url ''http://example.com/öpath''"
    renderMW(txt, 'url')

def test_headingss():
    txt = '\n\n'.join(['='*lvl + ' Heading lvl %d '% lvl + '='*lvl for lvl in range(1,6)])
    htmlcaptions = '\n\n'.join(['<h%(lvl)d>Heading h%(lvl)d</h%(lvl)d>' % {'lvl': lvl+1} for lvl in range(5)])
    txt += '\n\n' + htmlcaptions
    renderMW(txt, 'caption')

def test_lists():
    txt = u"* item 1 ä#üß\n* item 2 @€\n* item3\n\n# numbered item 1\n# numbered item 2\n# numbered item3"
    renderMW(txt, 'lists')

def test_table():
    txt='''{| class="prettytable"
|-
| row 1, col 1 || row 1, col 2 || row 1, col 3
|-
| row 2, col 1 || row 2, col 2 || row 2, col 3
|-
| row 3, col 1 || row 3, col 2 || row 3, col 3
'''
    renderMW(txt, 'table')

def test_preformatted():
    txt = """
 some preformatted text
 and some ascii 'art' #
                     # #
                    #   #
                     # #
                      #
 sometimes the text is too long to be displayed on a single line. we have to take care about this and either truncate or wrap the text
"""
    
    renderMW(txt, 'preformatted')

def test_indented():
    txt = 'normal paragraph\n\n: some indented text\n\nback to normal'
    renderMW(txt, 'indented')

def test_styles():
    txt = "''italic text'' and '''bold''' and the '''''mix''''' text<sup>sup tag</sup> and text<sub>sub tag</sub>"
    renderMW(txt, 'basicstyles')

def test_definitionlist():
    txt = '; definitionlist starts with definition term\n: the definition of the term follows\n; definitionlist starts with definition term\n: the definition of the term follows'
    renderMW(txt,'definitionlist')

             
def test_evilstyles():
    """MW markup guide says that these styles should be avoided.
    """
    txt = """text that is <big>big</big> and some is <small>small</small>. there is also <s>strike through</s> text
and <u>underlined text</u> linebreaks can be enforced<br/>here<br/>and here we had one. <nowiki>nowikitag ''allows'' the use of [[MW-syntax]] that is not interpreted</nowiki>. we can force <tt> typewriter mode</tt> or <code>code mode</code>"""

    renderMW(txt,'evilstyles')

def test_references():
    txt = 'random text with a reference<ref>here we have the reference text</ref>.\n\nwe need the references tag to print the references:\n\n<references/>'
    renderMW(txt, 'references')

def test_math():
    txt = u'some inline math formulas <math>\\frac{x+y}{xy}</math> and some more <math>x^{a+b}</math>\n\nindented formula:\n:<math>x=f(y^2+2).</math>'
    renderMW(txt, 'math')

def test_gallery():
    txt = []
    for perrow in range(2,6):
        for imgcount in range(4, 10):
            images = '\n'.join(['Bild:dummy_img%d.jpg' %i for i in range(imgcount)])
            t="""
<gallery perrow=%(perrow)d>
%(images)s
</gallery>
""" % {'perrow':perrow,
       'images':images}
            txt.append(t)
    renderMW('\n\n'.join(txt), 'gallery')
