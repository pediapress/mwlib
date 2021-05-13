#! /usr/bin/env py.test
# -*- coding: utf-8 -*-
import pytest

from mwlib import expander
from mwlib.expander import expandstr, DictDB
from mwlib.dummydb import DummyDB


def parse_and_show(s):
    res = expander.parse(s)
    print "PARSE:", repr(s)
    expander.show(res)
    return res


def test_noexpansion_inside_pre():
    res = expandstr("<pre>A{{Pipe}}B</pre>", "<pre>A{{Pipe}}B</pre>", wikidb=DictDB(Pipe="C"))
    print res


def test_undefined_variable():
    db = DictDB(Art="{{Pipe}}",
                Pipe="{{{undefined_variable}}}")

    te = expander.Expander(db.normalize_and_get_page(
        "Art", 0).rawtext, pagename="thispage", wikidb=db)
    res = te.expandTemplates()
    print "EXPANDED:", repr(res)
    assert u"{{{undefined_variable}}}" in res, "wrong expansion for undefined variable"


def test_birth_date_and_age():
    db = DictDB({
        "birth date and age": '[[ {{{3|{{{day|{{{3}}}}}}}}}]] [[{{{1|{{{year|{{{1}}}}}}}}}]]<font class="noprint"> (age&nbsp;{{age | {{{1|{{{year|{{{1}}}}}}}}} | {{{2|{{{month|{{{2}}}}}}}}} | {{{3|{{{day|{{{3}}}}}}}}} }})</font>',

        "age": '<includeonly>{{#expr:({{{4|{{CURRENTYEAR}}}}})-({{{1}}})-(({{{5|{{CURRENTMONTH}}}}})<({{{2}}})or({{{5|{{CURRENTMONTH}}}}})=({{{2}}})and({{{6|{{CURRENTDAY}}}}})<({{{3}}}))}}</includeonly>',
    })
    res = expandstr('{{birth date and age|1960|02|8}}', wikidb=db)

    print "EXPANDED:", repr(res)
    import datetime
    now = datetime.datetime.now()
    b = datetime.datetime(1960, 2, 8)
    age = now.year - b.year
    if now.month * 32 + now.day < b.month * 32 + b.day:
        age -= 1

    expected = u"age&nbsp;%s" % age
    assert expected in res


def test_five():
    txt = "text of the tnext template"
    db = DictDB(
        t1="{{{{{1}}}}}",
        tnext=txt)
    expandstr("{{t1|tnext}}", expected=txt, wikidb=db)


def test_five_parser():
    n = parse_and_show("{{{{{1}}}}}")
    assert isinstance(n, expander.Template)


def test_five_two_three():
    n = parse_and_show("{{{{{1}} }}}")
    assert isinstance(n, expander.Variable)


def test_five_three_two():
    n = parse_and_show("{{{{{1}}} }}")
    assert isinstance(n, expander.Template)


def test_alfred():
    """I start to hate that Alfred_Gusenbauer"""
    db = DictDB(
        a="{{ibox2|birth_date=1960}}",
        ibox2="{{{birth{{#if:{{{birthdate|}}}||_}}date}}}"
    )
    te = expander.Expander(db.normalize_and_get_page(
        "a", 0).rawtext, pagename="thispage", wikidb=db)
    res = te.expandTemplates()
    print "EXPANDED:", repr(res)
    assert "1960" in res


def test_switch_empty_fallback():
    expandstr("{{#switch:||foo=good}}", "good")


def test_switch_numeric_comparison():
    expandstr("{{ #switch: +07 | 7 = Yes | 007 = Bond | No }}", "Yes")


def test_switch_case_sensitive1():
    expandstr("{{ #switch: A | a=lower | A=UPPER }}", "UPPER")


def test_switch_case_sensitive2():
    expandstr("{{ #switch: A | a=lower | UPPER }}", "UPPER")


def test_switch_case_sensitive3():
    expandstr("{{ #switch: a | a=lower | UPPER }}", "lower")


def test_switch_fall_through():
    expandstr("{{#switch: a| a | b |c=first|default}}", "first")


def test_switch_fall_through_computed():
    expandstr("{{#switch:aaa|{{#if:1|aaa}}|b=fine}}", "fine")


def test_names_insensitive():
    expandstr("{{ #SWItch: A | a=lower | UPPER }}", "UPPER")


def test_ifeq_numeric_comparison():
    expandstr("{{ #ifeq: +07 | 007 | 1 | 0 }}", "1")


def test_ifeq_numeric_comparison2():
    expandstr('{{ #ifeq: "+07" | "007" | 1 | 0 }}', '0')


def test_ifeq_case_sensitive():
    expandstr("{{ #ifeq: A | a | 1 | 0 }}", "0")


def test_ifeq_strip():
    """http://code.pediapress.com/wiki/ticket/260"""
    expandstr("{{#ifeq: bla |    bla  |yes|no}}", "yes")


def test_ifexpr():
    expandstr("{{ #ifexpr: 10 > 9 | yes | no }}", "yes")


def test_expr_round():
    """round creates integers if it can"""
    expandstr("{{#expr: 10.0443 round -1}}", "10")


def test_expr_round2():
    expandstr("{{#expr: 10.0443 round 2}}", "10.04")


def test_too_many_args():
    expandstr("{{LC:AB|CD}}", "ab")


def test_lc_named_arg():
    expandstr("{{LC:a=AB|CD}}", "a=ab")


def test_named_variable_whitespace():
    """http://code.pediapress.com/wiki/ticket/23"""

    expandstr("{{doit|notable roles=these are the notable roles}}",
              "these are the notable roles",
              wikidb=DictDB(doit="{{{notable roles}}}"))


def test_pipe_inside_imagemap():
    """pipes inside image maps should not separate template arguments
    well, they do not separate arguments with the version running on en.wikipedia.org.
    they do separate arguments with the version running on pediapress.com:8080.
    (which is hopefully a newer version)
    """

    db = DictDB(
        sp="""{{#ifeq: {{{1}}} | 1
| <imagemap>
 Image:Padlock-silver-medium.svg|20px
 rect 0 0 1000 1000 [[Wikipedia:Protection policy|This page has been semi-protected from editing]]
 desc none
 </imagemap>
|bla
}}
""")
    result = expandstr("{{sp|1}}", wikidb=db)
    assert "</imagemap>" in result


def test_expand_comment():
    s = "foo\n     <!-- comment --->     \nbar"
    e = "foo\nbar"
    expandstr(s, e)


def test_tokenize_gallery():
    gall = """
<gallery caption="Sample gallery" widths="100px" heights="100px" perrow="6">
Image:Drenthe-Position.png|[[w:Drenthe|Drenthe]], the least crowded province
Image:Friesland-Position.png|[[w:Friesland|Friesland]] has many lakes
</gallery>
"""
    tokens = expander.tokenize(gall)
    g = tokens[1][1]
    assert g.startswith("<gallery")
    assert g.endswith("</gallery>")


def test_template_name_colon():
    """http://code.pediapress.com/wiki/ticket/36
    """
    p = parse_and_show("{{Template:foobar}}")
    assert isinstance(p, expander.Template), 'expected a template'
    assert p[0] == u'Template:foobar'


def test_expand_parser_func_name():
    expandstr("{{ {{NZ}}expr: 1+1}}", "2",
              wikidb=DictDB(NZ="#"))


def test_expand_name_with_colon():
    wikidb = DictDB()
    wikidb.d['bla:blubb'] = 'foo'
    expandstr("{{bla:blubb}}", "foo", wikidb=wikidb)


def test_parser_func_from_template():
    expandstr("{{ {{bla}} 1 + 1}}", "2", wikidb=DictDB(bla="#expr:"))


def test_bad_expr_name():
    s = expandstr("{{expr:1+1}}")  # '#' missing
    assert s != '2', "bad result"


def test_parmpart():
    parmpart = """{{#ifeq:/{{{2|}}}
|{{#titleparts:/{{{2|}}}|1|{{#expr:1+{{{1|1}}}}}}}
|
|{{#titleparts:/{{{2|}}}|1|{{#expr:1+{{{1|1}}}}}}}
}}"""
    expandstr("{{ParmPart|0|a/b}}", "", wikidb=DictDB(ParmPart=parmpart))
    expandstr("{{ParmPart|1|a/b}}", "a", wikidb=DictDB(ParmPart=parmpart))
    expandstr("{{ParmPart|2|a/b}}", "b", wikidb=DictDB(ParmPart=parmpart))
    expandstr("{{ParmPart|3|a/b}}", "", wikidb=DictDB(ParmPart=parmpart))


def test_titleparts():
    expandstr("{{#titleparts:Help:Link/a/b|0|}}", "Help:Link/a/b")
    expandstr("{{#titleparts:Help:Link/a/b|1|}}", "Help:Link")
    expandstr("{{#titleparts:Help:Link/a/b|2|}}", "Help:Link/a")
    expandstr("{{#titleparts:Help:Link/a/b|3|}}", "Help:Link/a/b")
    expandstr("{{#titleparts:Help:Link/a/b|4|}}", "Help:Link/a/b")


def test_titleparts_2params():
    expandstr("{{#titleparts:Help:Link/a/b|2|2}}", "a/b")
    expandstr("{{#titleparts:Help:Link/a/b|1|2}}", "a")
    expandstr("{{#titleparts:Help:Link/a/b|1|3}}", "b")


def test_titleparts_negative():
    expandstr("{{#titleparts:Help:Link/a/b|-1|}}", "Help:Link/a")
    expandstr("{{#titleparts:Help:Link/a/b|1|-1|}}", "b")


def test_titleparts_nonint():
    expandstr("{{#titleparts:Help:Link/a/b|bla}}", "Help:Link/a/b")

cases = [
("{{#iferror:{{#expr:1+1}}|bad input|valid expression}}", "valid expression"),
("{{#iferror:{{#expr:1+Z}}|bad input|valid expression}}", "bad input"),
("{{#iferror:{{#expr:1+1}}|bad input}}", "2"),
("{{#iferror:{{#expr:1+Z}}|bad input}}", "bad input"),
("{{#iferror:{{#expr:1+1}}}}", "2"),
("{{#iferror:{{#expr:1+Z}}}}", ""),
("{{#iferror:good|bad input|}}", ""),
]


@pytest.mark.parametrize("case", cases)
def test_iferror(case):
    expandstr(case[0], case[1])


def test_no_implicit_newline():
    expandstr("foo\n{{#if: 1|#bar}}", "foo\n#bar")
    expandstr("{{#if: 1|#bar}}", "#bar")


def test_implicit_newline_noinclude():
    expandstr("foo {{tt}}", "foo \n{|", wikidb=DictDB(tt="<noinclude></noinclude>{|"))


def test_implicit_newline_includeonly():
    expandstr("foo {{tt}}", "foo \n{|", wikidb=DictDB(tt="<includeonly>{|</includeonly>"))


def test_implicit_newline_begintable():
    expandstr("foo {{tt}}", "foo \n{|", wikidb=DictDB(tt="{|"))


def test_implicit_newline_colon():
    expandstr("foo {{tt}}", "foo \n:", wikidb=DictDB(tt=":"))


def test_implicit_newline_semicolon():
    expandstr("foo {{tt}}", "foo \n;", wikidb=DictDB(tt=";"))


def test_implicit_newline_ifeq():
    expandstr("{{#ifeq: 1 | 1 | foo {{#if: 1 | {{{!}} }}}}", "foo \n{|", wikidb=DictDB({"!": "|"}))


def test_empty_template():
    """test for http://code.pediapress.com/wiki/ticket/126"""
    expandstr("{{}}", "")


def test_implicit_newline_magic():
    expandstr("foo {{#if: 1 | :xxx }} bar", "foo \n:xxx bar")
    expandstr("foo {{#ifexpr: 1 | #xxx }} bar", "foo \n#xxx bar")


def test_implicit_newline_switch():
    """http://code.pediapress.com/wiki/ticket/386"""
    expandstr("* foo{{#switch:bar|bar=* bar}}", "* foo\n* bar")


def test_implicit_newline_inner():
    expandstr("ab {{#if: 1| cd {{#if:||#f9f9f9}}}} ef", "ab cd \n#f9f9f9 ef")
    expandstr("ab {{#switch: 1| 1=cd {{#if:||#f9f9f9}}}} ef", "ab cd \n#f9f9f9 ef")
    expandstr("ab{{#tag:imagemap|{{#if:1|#abc}} }}ef", "ab<imagemap>\n#abc </imagemap>ef")


def test_implicit_newline_param():
    """http://code.pediapress.com/wiki/ticket/877"""
    wikidb = DictDB(dict(foo="foo{{{1}}}", bar="{|", baz="|"))

    def doit(a, b):
        expandstr(a, b, wikidb=wikidb)

    doit("{{foo|{{bar}}}}", "foo\n{|")
    doit("{{foo|1={{bar}}}}", "foo{|")
    doit("{{foo|{{{baz}} }}", "foo{| ")
    doit("{{foo|\nbar\n}}baz", "foo\nbar\nbaz")
    doit("{{foo| bar }}baz", "foo bar baz")


def test_expand_after_named():
    db = DictDB(
        show="{{{1}}}",
        a="a=bc")
    expandstr("{{show|{{a}}}}", "a=bc", wikidb=db)


def test_padleft():
    expandstr("{{padleft:7|3|0}}", "007")
    expandstr("{{padleft:0|3|0}}", "000")
    expandstr("{{padleft:bcd|6|a}}", "aaabcd")
    expandstr("{{padleft:|3|abcde}}", "abc")
    expandstr("{{padleft:bla|5|xyz}}", "xybla")
    expandstr("{{padleft:longstring|3|abcde}}", "longstring")
    # {{padleft:cafe|8|-}} = ----cafe


def test_padright():
    expandstr("{{padright:bcd|6|a}}", "bcdaaa")
    expandstr("{{padright:0|6|a}}", "0aaaaa")
    expandstr("{{padright:|3|abcde}}", "abc")
    expandstr("{{padright:bla|5|xyz}}", "blaxy")
    expandstr("{{padright:longstring|3|abcde}}", "longstring")


def test_urlencode():
    expandstr('{{urlencode:x y @}}', 'x+y+%40')


def test_urlencode_non_ascii():
    expandstr(u'{{urlencode:L\xe9onie}}', 'L%C3%A9onie')


def test_anchorencode():
    """http://code.pediapress.com/wiki/ticket/213"""
    expandstr('{{anchorencode:x #y @}}', 'x_.23y_.40')


def test_anchorencode_non_ascii():
    expandstr(u"{{anchorencode:\u0107}}", ".C4.87")


def test_fullurl():
    expandstr('{{fullurl:x y @}}', 'http://en.wikipedia.org/wiki/X_y_%40')


def test_fullurl_nonascii():
    expandstr(u'{{fullurl:L\xe9onie}}', 'http://en.wikipedia.org/wiki/L%C3%A9onie')


def test_server():
    expandstr('{{server}}', 'http://en.wikipedia.org')


def test_servername():
    expandstr('{{servername}}', 'en.wikipedia.org')


def test_1x_newline_and_spaces():
    # see
    # http://en.wikipedia.org/wiki/Help:Newlines_and_spaces#Spaces_and.2For_newlines_as_value_of_an_unnamed_parameter
    wikidb = DictDB()
    wikidb.d['1x'] = '{{{1}}}'

    def e(a, b):
        return expandstr(a, b, wikidb=wikidb)

    e('a{{#if:1|\n}}b', 'ab')
    e('a{{#if:1|b\n}}c', 'abc')
    e('a{{#if:1|\nb}}c', 'abc')

    e('a{{1x|\n}}b', 'a\nb')
    e('a{{1x|b\n}}c', 'ab\nc')
    e('a{{1x|\nb}}c', 'a\nbc')

    e('a{{1x|1=\n}}b', 'ab')

    e('a{{1x|1=b\n}}c', 'abc')
    e('a{{1x|1=\nb}}c', 'abc')


def test_variable_alternative():
    wikidb = DictDB(t1='{{{var|undefined}}}')
    expandstr('{{t1|var=}}', '', wikidb=wikidb)


def test_implicit_newline_after_expand():
    wikidb = DictDB(tone='{{{1}}}{{{2}}}')
    expandstr('foo {{tone||:}} bar', 'foo \n: bar', wikidb=wikidb)


def test_pagename_non_ascii():
    def e(a, b):
        return expandstr(a, b, pagename=u'L\xe9onie s')
    e('{{PAGENAME}}', u'L\xe9onie s')
    e('{{PAGENAMEE}}', 'L%C3%A9onie_s')

    e('{{BASEPAGENAME}}', u'L\xe9onie s')
    e('{{BASEPAGENAMEE}}', 'L%C3%A9onie_s')

    e('{{FULLPAGENAME}}', u'L\xe9onie s')
    e('{{FULLPAGENAMEE}}', 'L%C3%A9onie_s')

    e('{{SUBPAGENAME}}', u'L\xe9onie s')
    e('{{SUBPAGENAMEE}}', 'L%C3%A9onie_s')


def test_get_templates():
    def doit(source, expected):
        r = expander.get_templates(source, u'')
        assert r == expected, "expected %r, got %r" % (expected, r)

    doit("{{foo| {{ bar }} }}", set("foo bar".split()))
    doit("{{foo{{{1}}} }}", set())
    doit("{{{ {{foo}} }}}", set(['foo']))
    doit("{{ #if: {{{1}}} |yes|no}}", set())


def test_noinclude_end():
    expandstr("{{foo}}", "foo", wikidb=DictDB(foo="foo<noinclude>bar should not be in expansion"))


def test_monthnumber():
    wikidb = DictDB(MONTHNUMBER="{{#if:{{{1|}}}|{{#switch:{{lc:{{{1}}}}}|january|jan=1|february|feb=2|march|mar=3|apr|april=4|may=5|june|jun=6|july|jul=7|august|aug=8|september|sep=9|october|oct=10|november|nov=11|december|dec=12|{{#ifexpr:{{{1}}}<0|{{#ifexpr:(({{{1}}})round 0)!=({{{1}}})|{{#expr:12-(((0.5-({{{1}}}))round 0)mod 12)}}|{{#expr:12-(((11.5-({{{1}}}))round 0)mod 12)}}}}|{{#expr:(((10.5+{{{1}}})round 0)mod 12)+1}}}}}}|Missing required parameter 1=''month''!}}")

    expandstr("{{MONTHNUMBER|12}}", "12", wikidb=wikidb)


def test_switch_default_template():
    expandstr("{{#switch:1|{{#if:1|5|12}}}}", "5")


def test_preserve_space_in_tag():
    expandstr("{{#tag:imagemap|cd }}", "<imagemap>cd </imagemap>")


def test_localurle_umlaut():
    """http://code.pediapress.com/wiki/ticket/473"""
    r = expandstr(u"{{LOCALURLE:F\xfcbar}}")
    assert r.endswith('/F%C3%BCbar')


def test_equal_inside_link():
    db = DictDB(t1="{{{1}}}")
    expandstr("{{t1|[[abc|foo=5]]}}", "[[abc|foo=5]]", wikidb=db)


def test_tag_parametrs():
    expandstr('{{#tag:test|contents|a=b|c=d}}', '<test a="b" c="d">contents</test>')
    expandstr("{{#tag:div|contents|a}}")


def test_rel2abs():
    expandstr("{{#rel2abs: ./quok | Help:Foo/bar/baz }}", "Help:Foo/bar/baz/quok")
    expandstr("{{#rel2abs: ../quok | Help:Foo/bar/baz }}", "Help:Foo/bar/quok")
    expandstr("{{#rel2abs: ../. | Help:Foo/bar/baz }}", "Help:Foo/bar")

    expandstr("{{#rel2abs: ../quok/. | Help:Foo/bar/baz }}", "Help:Foo/bar/quok")
    expandstr("{{#rel2abs: ../../quok | Help:Foo/bar/baz }}", "Help:Foo/quok")
    expandstr("{{#rel2abs: ../../../quok | Help:Foo/bar/baz }}", "quok")
    expandstr("{{#rel2abs: abc | foo}}", "abc")
    expandstr("{{#rel2abs: /abc | foo}}", "foo/abc")


def test_namespace():
    expandstr("{{NAMESPACE}}", "Benutzer", None, "User:Schmir")
    expandstr("{{NAMESPACE}}", "")
    expandstr("{{NAMESPACE:Mainz}}", "")
    expandstr("{{NAMESPACE:User_talk:Schmir}}", "Benutzer Diskussion")
    expandstr("{{NAMESPACE:User talk:Schmir}}", "Benutzer Diskussion")
    expandstr("{{NAMESPACE:  benutzer diskussion:Schmir}}", "Benutzer Diskussion")


def test_pagename():
    expandstr("{{PAGENAME}}", "Thispage")
    expandstr("{{PAGENAME|Mainz}}", "Mainz")
    expandstr("{{PAGENAME:User:Schmir}}", "Schmir")
    expandstr("{{PAGENAME:acdc}}", "Acdc")


def test_namespace_as_template_type_error():
    """https://github.com/pediapress/mwlib/issues/3"""
    expandstr("{{NAMESPACE|}}")
    expandstr("{{NAMESPACE|foo}}")
    expandstr("{{NAMESPACE|foo|bla}}")
    expandstr("{{NAMESPACE||bla}}")


def test_preprocess_uniq_after_comment():
    s = u"""
<!--
these <ref> tags should be ignored: <ref>
-->

foo was missing<ref>bar</ref> <!-- some comment--> baz


<references />
"""
    e = expander.Expander(s, pagename="test", wikidb=DictDB())
    raw = e.expandTemplates()
    print repr(raw)
    assert u"foo was missing" in raw, "text is missing"


def test_dynamic_parserfun():
    expandstr("{{{{#if: 1|}}#time: Y-m-d | 2009-1-2}}", "2009-01-02")

    expandstr("{{{{#if: 1|}}#switch: A | a=lower | A=UPPER }}", "UPPER")

    expandstr("{{{{#if: 1|}}#if: 1 | yes}}", "yes")


def test_iferror_switch_default():
    """http://code.pediapress.com/wiki/ticket/648"""
    expandstr("{{#iferror: [[foo {{bar}}]] | yes|no}}", "no")
    expandstr(u"""{{#switch: bla
| #default = {{#iferror: [[foo {{bar}}]] | yes|no}}
}}""", "no")


def test_variable_subst():
    expandstr("{{{{{subst|}}}#if: 1| yes| no}}", "yes")
    expandstr("{{{{{subst|}}}#expr: 1+1}}", "2")
    expandstr("{{{{{susbst|}}}#ifexpr: 1+1|yes|no}}", "yes")


def test_link_vs_expander():
    """http://code.pediapress.com/wiki/ticket/752"""
    expandstr("{{#if: 1|  [[foo|bar}}123", "{{#if: 1|  [[foo|bar}}123")


def test_pagemagic():
    def expand_page(tpl, expected):
        return expandstr('{{%s}}' % tpl, expected,
                         pagename='Benutzer:Anonymous user!/sandbox/my page')

    def expand_talk(tpl, expected):
        return expandstr('{{%s}}' % tpl, expected,
                         pagename='Benutzer Diskussion:Anonymous user!/sandbox/my page')

    expand_page('PAGENAME', 'Anonymous user!/sandbox/my page')
    expand_page('PAGENAMEE', 'Anonymous_user%21/sandbox/my_page')
    expand_talk('PAGENAME', 'Anonymous user!/sandbox/my page')
    expand_talk('PAGENAMEE', 'Anonymous_user%21/sandbox/my_page')
    expand_page('BASEPAGENAME', 'Anonymous user!/sandbox')
    expand_page('BASEPAGENAMEE', 'Anonymous_user%21/sandbox')
    expand_talk('BASEPAGENAME', 'Anonymous user!/sandbox')
    expand_talk('BASEPAGENAMEE', 'Anonymous_user%21/sandbox')
    expand_page('SUBPAGENAME', 'my page')
    expand_page('SUBPAGENAMEE', 'my_page')
    expand_talk('SUBPAGENAME', 'my page')
    expand_talk('SUBPAGENAMEE', 'my_page')
    expand_page('NAMESPACE', 'Benutzer')
    expand_page('NAMESPACEE', 'Benutzer')
    expand_talk('NAMESPACE', 'Benutzer Diskussion')
    expand_talk('NAMESPACEE', 'Benutzer_Diskussion')
    expand_page('FULLPAGENAME', 'Benutzer:Anonymous user!/sandbox/my page')
    expand_page('FULLPAGENAMEE', 'Benutzer%3AAnonymous_user%21/sandbox/my_page')
    expand_talk('FULLPAGENAME', 'Benutzer Diskussion:Anonymous user!/sandbox/my page')
    expand_talk('FULLPAGENAMEE', 'Benutzer_Diskussion%3AAnonymous_user%21/sandbox/my_page')
    expand_page('TALKSPACE', 'Benutzer Diskussion')
    expand_page('TALKSPACEE', 'Benutzer_Diskussion')
    expand_talk('TALKSPACE', 'Benutzer Diskussion')
    expand_talk('TALKSPACEE', 'Benutzer_Diskussion')
    expand_page('SUBJECTSPACE', 'Benutzer')
    expand_page('SUBJECTSPACEE', 'Benutzer')
    expand_talk('SUBJECTSPACE', 'Benutzer')
    expand_talk('SUBJECTSPACEE', 'Benutzer')
    expand_page('ARTICLESPACE', 'Benutzer')
    expand_page('ARTICLESPACEE', 'Benutzer')
    expand_talk('ARTICLESPACE', 'Benutzer')
    expand_talk('ARTICLESPACEE', 'Benutzer')
    expand_page('TALKPAGENAME', 'Benutzer Diskussion:Anonymous user!/sandbox/my page')
    expand_page('TALKPAGENAMEE', 'Benutzer_Diskussion%3AAnonymous_user%21/sandbox/my_page')
    expand_talk('TALKPAGENAME', 'Benutzer Diskussion:Anonymous user!/sandbox/my page')
    expand_talk('TALKPAGENAMEE', 'Benutzer_Diskussion%3AAnonymous_user%21/sandbox/my_page')
    expand_page('SUBJECTPAGENAME', 'Benutzer:Anonymous user!/sandbox/my page')
    expand_page('SUBJECTPAGENAMEE', 'Benutzer%3AAnonymous_user%21/sandbox/my_page')
    expand_talk('SUBJECTPAGENAME', 'Benutzer:Anonymous user!/sandbox/my page')
    expand_talk('SUBJECTPAGENAMEE', 'Benutzer%3AAnonymous_user%21/sandbox/my_page')
    expand_page('ARTICLEPAGENAME', 'Benutzer:Anonymous user!/sandbox/my page')
    expand_page('ARTICLEPAGENAMEE', 'Benutzer%3AAnonymous_user%21/sandbox/my_page')
    expand_talk('ARTICLEPAGENAME', 'Benutzer:Anonymous user!/sandbox/my page')
    expand_talk('ARTICLEPAGENAMEE', 'Benutzer%3AAnonymous_user%21/sandbox/my_page')


def test_pagemagic_with_arg():
    def expand_page(tpl, expected):
        return expandstr('{{%s:%s}}' % (tpl, 'Benutzer:Anonymous user!/sandbox/my page'),
                         expected, pagename='Help:Irrelevant')

    def expand_talk(tpl, expected):
        return expandstr('{{%s:%s}}' % (tpl, 'Benutzer Diskussion:Anonymous user!/sandbox/my page'),
                         expected, pagename='Help:Irrelevant')

    expand_page('PAGENAME', 'Anonymous user!/sandbox/my page')
    expand_page('PAGENAMEE', 'Anonymous_user%21/sandbox/my_page')
    expand_talk('PAGENAME', 'Anonymous user!/sandbox/my page')
    expand_talk('PAGENAMEE', 'Anonymous_user%21/sandbox/my_page')
    expand_page('BASEPAGENAME', 'Anonymous user!/sandbox')
    expand_page('BASEPAGENAMEE', 'Anonymous_user%21/sandbox')
    expand_talk('BASEPAGENAME', 'Anonymous user!/sandbox')
    expand_talk('BASEPAGENAMEE', 'Anonymous_user%21/sandbox')
    expand_page('SUBPAGENAME', 'my page')
    expand_page('SUBPAGENAMEE', 'my_page')
    expand_talk('SUBPAGENAME', 'my page')
    expand_talk('SUBPAGENAMEE', 'my_page')
    expand_page('NAMESPACE', 'Benutzer')
    expand_page('NAMESPACEE', 'Benutzer')
    expand_talk('NAMESPACE', 'Benutzer Diskussion')
    expand_talk('NAMESPACEE', 'Benutzer_Diskussion')
    expand_page('FULLPAGENAME', 'Benutzer:Anonymous user!/sandbox/my page')
    expand_page('FULLPAGENAMEE', 'Benutzer%3AAnonymous_user%21/sandbox/my_page')
    expand_talk('FULLPAGENAME', 'Benutzer Diskussion:Anonymous user!/sandbox/my page')
    expand_talk('FULLPAGENAMEE', 'Benutzer_Diskussion%3AAnonymous_user%21/sandbox/my_page')
    expand_page('TALKSPACE', 'Benutzer Diskussion')
    expand_page('TALKSPACEE', 'Benutzer_Diskussion')
    expand_talk('TALKSPACE', 'Benutzer Diskussion')
    expand_talk('TALKSPACEE', 'Benutzer_Diskussion')
    expand_page('SUBJECTSPACE', 'Benutzer')
    expand_page('SUBJECTSPACEE', 'Benutzer')
    expand_talk('SUBJECTSPACE', 'Benutzer')
    expand_talk('SUBJECTSPACEE', 'Benutzer')
    expand_page('ARTICLESPACE', 'Benutzer')
    expand_page('ARTICLESPACEE', 'Benutzer')
    expand_talk('ARTICLESPACE', 'Benutzer')
    expand_talk('ARTICLESPACEE', 'Benutzer')
    expand_page('TALKPAGENAME', 'Benutzer Diskussion:Anonymous user!/sandbox/my page')
    expand_page('TALKPAGENAMEE', 'Benutzer_Diskussion%3AAnonymous_user%21/sandbox/my_page')
    expand_talk('TALKPAGENAME', 'Benutzer Diskussion:Anonymous user!/sandbox/my page')
    expand_talk('TALKPAGENAMEE', 'Benutzer_Diskussion%3AAnonymous_user%21/sandbox/my_page')
    expand_page('SUBJECTPAGENAME', 'Benutzer:Anonymous user!/sandbox/my page')
    expand_page('SUBJECTPAGENAMEE', 'Benutzer%3AAnonymous_user%21/sandbox/my_page')
    expand_talk('SUBJECTPAGENAME', 'Benutzer:Anonymous user!/sandbox/my page')
    expand_talk('SUBJECTPAGENAMEE', 'Benutzer%3AAnonymous_user%21/sandbox/my_page')
    expand_page('ARTICLEPAGENAME', 'Benutzer:Anonymous user!/sandbox/my page')
    expand_page('ARTICLEPAGENAMEE', 'Benutzer%3AAnonymous_user%21/sandbox/my_page')
    expand_talk('ARTICLEPAGENAME', 'Benutzer:Anonymous user!/sandbox/my page')
    expand_talk('ARTICLEPAGENAMEE', 'Benutzer%3AAnonymous_user%21/sandbox/my_page')


def test_ns():
    """http://code.pediapress.com/wiki/ticket/902"""
    expandstr("{{NS:2}}", "Benutzer")


def test_localized_expander():
    db = DummyDB("nl")
    e = expander.Expander(u"{{#als: 1 | yes | no}}", wikidb=db)
    res = e.expandTemplates()
    assert res == "yes"


def test_localized_switch_default():
    db = DummyDB("nl")
    e = expander.Expander(u"{{#switch: 1 | #standaard=foobar}}", wikidb=db)
    res = e.expandTemplates()
    assert res == "foobar"


def test_localized_expr():
    db = DummyDB("nl")
    e = expander.Expander(u"{{#expressie: 1+2*3}}", wikidb=db)
    res = e.expandTemplates()
    assert res == "7"


def test_resolve_magic_alias():
    db = DummyDB("nl")
    e = expander.Expander(u"{{#als: 1 | yes | no}}", wikidb=db)
    assert e.resolve_magic_alias(u"#als") == u"#if"
    assert e.resolve_magic_alias(u"#foobar") is None


def test_safesubst():
    expandstr("{{safesubst:#expr:1+2}}", "3")
    expandstr("{{{{{|safesubst:}}}#expr:1+3}}", "4")
    expandstr("{{safesubst:#if: 1| yes | no}}", "yes")
