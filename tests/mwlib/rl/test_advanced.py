#! /usr/bin/env py.test

# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.


from pygments import highlight, lexers
from renderhelper import renderMW

from mwlib.writers.rl.rlsourceformatter import ReportlabFormatter

# node combinations: Table, Paragraph, PreFormatted, Emphasized, Definitionlist, Indented, Blockquote, Link,  URL, NamedURL,
# CategoryLink, LangLink, Image, Gallery, Source, Code, Teletyped, BR, References, Div, Span, ItemList, Math
# styles: Emphasized, Strong, overline, underline, sub, sup, small, big, cite, Center, Strike


nastyChars = "%(stylestart)sUmlauts: äöüÖÄÜß chinese: 应急机制构筑救灾长城 arabic: عيون المواقع : صحافة و إعلام %(styleend)s"
links = (
    "Link: [[MWArticleTitle]] plus anchor text: [[MWArticleTitle|%(nasty)s]] NamedURL: [http://example.com]  plus anchor text: [http://example.com %(nasty)s] URL: http://example.com"
    % {"nasty": nastyChars}
)


def get_styled_text(txt):
    txt_list = []
    for style in ["", "''", "'''", "<u>"]:
        styleend = style if style.find("<") == -1 else style[0] + "/" + style[1:]
        t = txt % {"stylestart": style, "styleend": styleend}
        txt_list.append(t)
    return txt_list


def test_list_and_tables_3():
    # oversized table -> nested table is rendered in plain-text
    txt = f"""
{{| class="prettytable"
|-
|
* lvl 1 {links}
* lvl 1
** lvl 2 {links}
** lvl 2
*** <math>-2=\\sqrt[3]{{-8}}\ne\\sqrt[6]{{(-8)^2}}=\\sqrt[6]{{64}}=+2.</math>
*** {links}
** lvl 2
** lvl 2
* lvl 1
|
{{| class="prettytable"
|-
|
# lvl 1 
# lvl 1
## lvl 2
## lvl 2 
### <tt>teletyped text</tt>
### lvl 3
## lvl 2
## lvl 2
# lvl 1
| text
|-
| text || <math>-2=\\sqrt[3]{{-8}}\ne\\sqrt[6]{{(-8)^2}}=\\sqrt[6]{{64}}=+2.</math>
|}}
|-
|text after nesting || {links}
|}}
"""
    renderMW("\n\n".join(get_styled_text(txt)), "lists_and_tables_3")


def test_list_and_tables_2():
    # oversized table -> nested table is rendered in plain-text
    txt = f"""
{{| class="prettytable"
|-
|
* lvl 1 {links}
* lvl 1
** lvl 2 {links}
** lvl 2
*** <math>-2=\\sqrt[3]{{-8}}\ne\\sqrt[6]{{(-8)^2}}=\\sqrt[6]{{64}}=+2.</math>
*** {links}
** lvl 2
** lvl 2
* lvl 1
|
{{| class="prettytable"
|-
|
# lvl 1 {links}
# lvl 1
## lvl 2
## lvl 2 {links}
### <tt>teletyped text</tt>
### {links}
## lvl 2
## lvl 2
# lvl 1
| text
|-
| text || <math>-2=\\sqrt[3]{{-8}}\ne\\sqrt[6]{{(-8)^2}}=\\sqrt[6]{{64}}=+2.</math>
|}}
|-
|text after nesting || {links}
|}}
"""
    renderMW("\n\n".join(get_styled_text(txt)), "lists_and_tables_2")


def test_list_and_tables_1():
    txt = f"""
some text outside a table
   
{{| class="prettytable"
|-
|
* lvl 1 {nastyChars}
* lvl 1
** lvl 2 {nastyChars}
** lvl 2
*** lvl 3
*** {nastyChars}
** lvl 2
** lvl 2
* lvl 1
|
# lvl 1 {nastyChars}
# lvl 1
## lvl 2
## lvl 2 {nastyChars}
### lvl 3
### {nastyChars}
## lvl 2
## lvl 2
# lvl 1
|}}
"""
    renderMW("\n\n".join(get_styled_text(txt)), "lists_and_tables_1")


def test_link_and_lists():
    txt = f"""
== Lists ==

# {links}
# plain text
## lvl2: {links}
## lvl 2: plain text

* {links}
* plain text
** lvl2: {links}
** lvl 2: plain text
"""

    renderMW("\n\n".join(get_styled_text(txt)), "links_and_lists")


def test_link_in_table():
    txt = f"""
== Table ==

{{| class="prettytable"
|-
| 1.1 || {links}
|-
| {links} || 2.2
|}}

{{| class="prettytable"
|-
| colspan="2" | colspanned cell
|-
| 2.1 || 2.2
|-
| colspan="2" |
{{| class="prettytable"
|-
| {links} || nested
|-
| bla || blub
|}}

|}}
"""

    renderMW("\n\n".join(get_styled_text(txt)), "links_and_tables")


def test_math_advanced():

    txt = """
inline math follows <math>-2=\\sqrt[3]{-8}\ne\\sqrt[6]{(-8)^2}=\\sqrt[6]{64}=+2.</math> and now text.

;indented math in definition list
:<math>-2=\\sqrt[3]{-8}\ne\\sqrt[6]{(-8)^2}=\\sqrt[6]{64}=+2.</math>

math in table (test down-scaling of formula):

{| class="prettytable"
|-
|<math>-2=\\sqrt[3]{-8}\ne\\sqrt[6]{(-8)^2}=\\sqrt[6]{64}=+2.</math>
|text
|-
| text
| text
|}
"""
    renderMW(txt, "math_advanced")


def test_entity_links():
    txt = "[http://toolserver.org/~magnus/geo/geohack.php?pagename=HMS_Cardiff_(D108)&params=-51.783600_N_-58.467786_E_]"

    renderMW(txt, "links_entities")


def test_category_links():
    """test for http://code.pediapress.com/wiki/ticket/177"""
    txt = "[[:Category:foo bar]]"
    renderMW(txt, "links_entities")


def test_breaking_long_sections():
    """test for http://code.pediapress.com/wiki/ticket/177"""
    txt = "= sect1/Bla/blub/wurst/bier&尚書•梓材&sdg/&bla/bl&b/aslkjfasdfafasFAS/fasdfasf/asdfs&asdf ="
    renderMW(txt, "breaking_long_sections")


def test_preformatted():
    txt = """
<pre>
  bla blub
   blub blub
    blub blub blub
</pre>
"""
    renderMW(txt, "preformatted")


def test_preformatted_breaking():

    txt = """
<pre>
<?xml version="1.0" standalone="yes" ?>
<DBMODEL Version="4.0">
<SETTINGS>
<GLOBALSETTINGS ModelName="posperDbdRev423" IDModel="0" IDVersion="0" VersionStr="1.0.0.0" Comments="" UseVersionHistroy="1" AutoIncVersion="1" DatabaseType="MySQL" ZoomFac="91.00" XPos="566" YPos="922" DefaultDataType="5" DefaultTablePrefix="0" DefSaveDBConn="" DefSyncDBConn="" DefQueryDBConn="" Printer="" HPageCount="4.0" PageAspectRatio="1.440892512336408" PageOrientation="1" PageFormat="A4 (210x297 mm, 8.26x11.7 inches)" SelectedPages="" UsePositionGrid="0" PositionGridX="20" PositionGridY="20" TableNameInRefs="1" DefaultTableType="0" ActivateRefDefForNewRelations="1" FKPrefix="" FKPostfix="" CreateFKRefDefIndex="1" DBQuoteCharacter="`" CreateSQLforLinkedObjects="0" DefModelFont="nimbus sans l" CanvasWidth="4096" CanvasHeight="2842" />

</pre>"""
    renderMW(txt, "preformatted_breaking")


def test_source():
    txt = """
<source lang="python">
print "hello world"
for i in range(42):
    print "go syntax highlighting"
</source>

<source lang="cpp">
#include <iostream>
#include <ostream>

int main() 
{
   std::cout << "Hallo Welt!" << std::endl;
}
</source>

<source lang="lolCode">
HAI
CAN HAS STDIO?
VISIBLE "HAI WORLD!"
KTHXBYE
</source>
"""

    renderMW(txt, "source")


def test_source_breaking():
    txt = """
<source lang="python">
print "asdkfj asöfkdlj asökdlfj asöklfj asöfja sölfjk aösljkdf aösljkf aöslkjf aöskfj aösjf aöskljf asöljf asöljf aösjf asöljkf aösldjf aösljkdf aösljf aösljdf öasljkf öasljdf öaslkjf aösljkf aösljf aösljf aösljf aösjkdf aöslk jfaösld jfaösljkdf aösljdf aösldjf aösldkjfaösldjfaösldjaösljdfaösldjfsal
print "this does not make any sense"
while True:
    print "assfaö ljkf asödfjk öklqejw tröqwlktj eq.r,tnm.,mnxcyvbxcvb,mnödfgjheritu epoitur eoqtur eökrlt ne,rm tnewötn _$§5 5345 23$! $%$§% 1ö43jh sadflkjahsdf asjdfhasd flkjahs fajsklfhljkh435pietruqüwirqwoeiräqäöi1o4i123i45j1245 oi51 oi1u345 o3i14u 5 "
</source>
"""
    renderMW(txt, "source_breaking")


def test_source_pygments():
    source = """\

while True:
  print 'this is python'

"""
    formatter = ReportlabFormatter(
        font_size=10,
        font_name="FreeMono",
        line_numbers=False,
        background_color="#eeeeee",
    )
    formatter.encoding = "utf-8"
    lexer = lexers.get_lexer_by_name("python")

    out_expected = (
        '<para backcolor="#eeeeee"><font name="FreeMono" size="10"><font '
        'color="#008000"><b>while</b></font> <font '
        'color="#008000"><b>True</b></font>:<font color="#bbbbbb">\n'
        '</font>  <font color="#008000">print</font> <font color="#BA2121">\'this is '
        'python\'</font><font color="#bbbbbb">\n'
        "</font></font></para>\n"
    )

    out_pygments = highlight(source, lexer, formatter)
    assert out_pygments.decode() == out_expected
