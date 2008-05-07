#! /usr/bin/env py.test

from mwlib import expander
from mwlib.expander import expandstr, DictDB

def parse_and_show(s):
    res=expander.parse(s)
    print "PARSE:", repr(s)    
    expander.show(res)
    return res

def test_noexpansion_inside_pre():
    db = DictDB(Art="<pre>A{{Pipe}}B</pre>",
                Pipe="C")

    res = expandstr("<pre>A{{Pipe}}B</pre>", "<pre>A{{Pipe}}B</pre>", wikidb=DictDB(Pipe="C"))


def test_undefined_variable():
    db = DictDB(Art="{{Pipe}}",
                Pipe="{{{undefined_variable}}}")
    
    te = expander.Expander(db.getRawArticle("Art"), pagename="thispage", wikidb=db)
    res = te.expandTemplates()
    print "EXPANDED:", repr(res)
    assert u"{{{undefined_variable}}}" in res, "wrong expansion for undefined variable"

def test_birth_date_and_age():
    db = DictDB({
            "birth date and age": '[[{{MONTHNAME|{{{2|{{{month|{{{2}}}}}}}}}}} {{{3|{{{day|{{{3}}}}}}}}}]] [[{{{1|{{{year|{{{1}}}}}}}}}]]<font class="noprint"> (age&nbsp;{{age | {{{1|{{{year|{{{1}}}}}}}}} | {{{2|{{{month|{{{2}}}}}}}}} | {{{3|{{{day|{{{3}}}}}}}}} }})</font>',
            
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

    assert u"February" in res
    
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

def test_monthname():
    expandstr("{{MONTHNAME|1}}", "January")
    expandstr("{{MONTHNAME|2}}", "February")
    expandstr("{{MONTHNAME|12}}", "December")
    expandstr("{{MONTHNAME|13}}", "January")

    expandstr("{{MONTHNAME|0}}", "December")

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


def test_iferror():
    expandstr("{{#iferror:{{#expr:1+1}}|bad input|valid expression}}", "valid expression")
    expandstr("{{#iferror:{{#expr:1+Z}}|bad input|valid expression}}", "bad input")
    expandstr("{{#iferror:{{#expr:1+1}}|bad input}}", "2")
    expandstr("{{#iferror:{{#expr:1+Z}}|bad input}}", "bad input")
    expandstr("{{#iferror:{{#expr:1+1}}}}", "2")
    expandstr("{{#iferror:{{#expr:1+Z}}}}", "")

def test_implicit_newline_begintable():
    expandstr("foo {{tt}}", "foo \n{|", wikidb=DictDB(tt="{|"))
    
def test_implicit_newline_colon():
    expandstr("foo {{tt}}", "foo \n:", wikidb=DictDB(tt=":"))

def test_implicit_newline_semicolon():
    expandstr("foo {{tt}}", "foo \n;", wikidb=DictDB(tt=";"))
