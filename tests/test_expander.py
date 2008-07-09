#! /usr/bin/env py.test

from mwlib import expander
from mwlib.expander import expandstr, DictDB
from mwlib.xfail import xfail

        
def parse_and_show(s):
    res=expander.parse(s)
    print "PARSE:", repr(s)    
    expander.show(res)
    return res

def test_noexpansion_inside_pre():
    db = DictDB(Art="<pre>A{{Pipe}}B</pre>",
                Pipe="C")

    res = expandstr("<pre>A{{Pipe}}B</pre>", "<pre>A{{Pipe}}B</pre>", wikidb=DictDB(Pipe="C"))

@xfail
def test_undefined_variable():
    db = DictDB(Art="{{Pipe}}",
                Pipe="{{{undefined_variable}}}")
    
    te = expander.Expander(db.getRawArticle("Art"), pagename="thispage", wikidb=db)
    res = te.expandTemplates()
    print "EXPANDED:", repr(res)
    assert u"{{{undefined_variable}}}" in res, "wrong expansion for undefined variable"

def test_birth_date_and_age():
    db = DictDB({
            "birth date and age": '[[ {{{3|{{{day|{{{3}}}}}}}}}]] [[{{{1|{{{year|{{{1}}}}}}}}}]]<font class="noprint"> (age&nbsp;{{age | {{{1|{{{year|{{{1}}}}}}}}} | {{{2|{{{month|{{{2}}}}}}}}} | {{{3|{{{day|{{{3}}}}}}}}} }})</font>',
            
            "age" : '<includeonly>{{#expr:({{{4|{{CURRENTYEAR}}}}})-({{{1}}})-(({{{5|{{CURRENTMONTH}}}}})<({{{2}}})or({{{5|{{CURRENTMONTH}}}}})=({{{2}}})and({{{6|{{CURRENTDAY}}}}})<({{{3}}}))}}</includeonly>',
            })
    res=expandstr('{{birth date and age|1960|02|8}}', wikidb=db)

    print "EXPANDED:", repr(res)
    import datetime
    now=datetime.datetime.now()
    b=datetime.datetime(1960,2,8)
    age = now.year-b.year
    if now.month*32+now.day < b.month*32+b.day:
        age -= 1
    
    expected = u"age&nbsp;%s" % age
    assert expected in res

    
def test_five():
    txt = "text of the tnext template"
    db=DictDB(
        t1="{{{{{1}}}}}",
        tnext=txt)
    expandstr("{{t1|tnext}}", expected=txt, wikidb=db)

def test_five_parser():
    n=parse_and_show("{{{{{1}}}}}")
    assert isinstance(n, expander.Template)

def test_five_two_three():
    n=parse_and_show("{{{{{1}} }}}")
    assert isinstance(n, expander.Variable)

def test_five_three_two():
    n=parse_and_show("{{{{{1}}} }}")
    assert isinstance(n, expander.Template)

    
def test_alfred():
    """I start to hate that Alfred_Gusenbauer"""
    db = DictDB(
        a="{{ibox2|birth_date=1960}}",
        ibox2="{{{birth{{#if:{{{birthdate|}}}||_}}date}}}"
        )
    te = expander.Expander(db.getRawArticle("a"), pagename="thispage", wikidb=db)
    res = te.expandTemplates()
    print "EXPANDED:", repr(res)
    assert "1960" in res

def test_switch_numeric_comparison():
    expandstr("{{ #switch: +07 | 7 = Yes | 007 = Bond | No }}", "Yes")

def test_switch_case_sensitive1():
    expandstr("{{ #switch: A | a=lower | A=UPPER }}", "UPPER")

def test_switch_case_sensitive2():
    expandstr("{{ #switch: A | a=lower | UPPER }}", "UPPER")

def test_switch_case_sensitive3():
    expandstr("{{ #switch: a | a=lower | UPPER }}", "lower")

def test_names_insensitive():
    expandstr("{{ #SWItch: A | a=lower | UPPER }}", "UPPER")

def test_ifeq_numeric_comparison():
    expandstr("{{ #ifeq: +07 | 007 | 1 | 0 }}", "1")

def test_ifeq_numeric_comparison2():
    expandstr('{{ #ifeq: "+07" | "007" | 1 | 0 }}', '0')

def test_ifeq_case_sensitive():
    expandstr("{{ #ifeq: A | a | 1 | 0 }}", "0")

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
    result=expandstr("{{sp|1}}", wikidb=db)
    assert "</imagemap>" in result


def test_expand_comment():
    s="foo\n     <!-- comment --->     \nbar"
    e="foo\nbar"
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
    p=parse_and_show("{{Template:foobar}}")
    assert isinstance(p, expander.Template), 'expected a template'
    assert len(p.children)==1, 'expected exactly one child'
    


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
    s=expandstr("{{expr:1+1}}")  # '#' missing
    assert s!='2', "bad result"

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
    
def test_iferror():
    expandstr("{{#iferror:{{#expr:1+1}}|bad input|valid expression}}", "valid expression")
    expandstr("{{#iferror:{{#expr:1+Z}}|bad input|valid expression}}", "bad input")
    expandstr("{{#iferror:{{#expr:1+1}}|bad input}}", "2")
    expandstr("{{#iferror:{{#expr:1+Z}}|bad input}}", "bad input")
    expandstr("{{#iferror:{{#expr:1+1}}}}", "2")
    expandstr("{{#iferror:{{#expr:1+Z}}}}", "")

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

def test_empty_template():
    """test for http://code.pediapress.com/wiki/ticket/126"""
    expandstr("{{}}", "")
    
def test_implicit_newline_magic():
    expandstr("foo {{#if: 1 | :xxx }} bar", "foo \n:xxx bar")
    expandstr("foo {{#ifexpr: 1 | #xxx }} bar", "foo \n#xxx bar")
    
def test_expand_after_named():
    db = DictDB(
        show="{{{1}}}",
        a="a=bc")
    expandstr("{{show|{{a}}}}", "a=bc",  wikidb=db)
    
def test_padleft():
    yield expandstr, "{{padleft:7|3|0}}", "007"
    yield expandstr, "{{padleft:0|3|0}}", "000"
    yield expandstr, "{{padleft:bcd|6|a}}", "aaabcd"
    # {{padleft:cafe|8|-}} = ----cafe 

def test_padright():   
    yield expandstr, "{{padright:bcd|6|a}}", "bcdaaa"
    yield expandstr, "{{padright:0|6|a}}", "0aaaaa"
    
def test_urlencode():
    expandstr('{{urlencode:x y @}}', 'x+y+%40')
    
def test_urlencode_non_ascii():
    expandstr(u'{{urlencode:L\xe9onie}}', 'L%C3%A9onie')

@xfail
def test_anchorencode():
    """http://code.pediapress.com/wiki/ticket/213"""
    expandstr('{{anchorencode:x #y @}}', 'x_.23y_.40')
    
def test_fullurl():
    expandstr('{{fullurl:x y @}}', 'http://en.wikipedia.org/wiki/X_y_%40')

def test_fullurl_nonascii():
    expandstr(u'{{fullurl:L\xe9onie}}', 'http://en.wikipedia.org/wiki/L%C3%A9onie')
              
def test_server():
    expandstr('{{server}}', 'http://en.wikipedia.org')
    
def test_servername():
    expandstr('{{servername}}', 'en.wikipedia.org')

    
def test_1x_newline_and_spaces():
    # see http://en.wikipedia.org/wiki/Help:Newlines_and_spaces#Spaces_and.2For_newlines_as_value_of_an_unnamed_parameter
    wikidb=DictDB()
    wikidb.d['1x'] = '{{{1}}}'
    def e(a,b):
        return expandstr(a,b,wikidb=wikidb)

    yield e, 'a{{#if:1|\n}}b', 'ab'
    yield e, 'a{{#if:1|b\n}}c', 'abc'
    yield e, 'a{{#if:1|\nb}}c', 'abc'
    
            
    yield e, 'a{{1x|\n}}b', 'a\nb'
    yield e, 'a{{1x|b\n}}c', 'ab\nc'
    yield e, 'a{{1x|\nb}}c', 'a\nbc'

    yield e, 'a{{1x|1=\n}}b', 'ab'

    yield e, 'a{{1x|1=b\n}}c', 'abc'
    yield e, 'a{{1x|1=\nb}}c', 'abc'



def test_variable_alternative():
    wikidb=DictDB(t1='{{{var|undefined}}}')
    expandstr('{{t1|var=}}', '', wikidb=wikidb)
    
def test_implicit_newline_after_expand():
    wikidb=DictDB(tone='{{{1}}}{{{2}}}')
    expandstr('foo {{tone||:}} bar', 'foo \n: bar', wikidb=wikidb)
    
def test_pagename_non_ascii():
    def e(a,b):
        return expandstr(a,b,pagename=u'L\xe9onie s')
    yield e, '{{PAGENAME}}', u'L\xe9onie s'
    yield e, '{{PAGENAMEE}}', 'L%C3%A9onie_s'

    yield e, '{{BASEPAGENAME}}', u'L\xe9onie s'
    yield e, '{{BASEPAGENAMEE}}', 'L%C3%A9onie_s'

    
    yield e, '{{FULLPAGENAME}}', u'L\xe9onie s'
    yield e, '{{FULLPAGENAMEE}}', 'L%C3%A9onie_s'
    
    yield e, '{{SUBPAGENAME}}', u'L\xe9onie s'
    yield e, '{{SUBPAGENAMEE}}', 'L%C3%A9onie_s'
