#! /usr/bin/env py.test

from mwlib.refine import core
from mwlib import nshandling
from mwlib.xfail import xfail

tokenize = core.tokenize
show = core.show
T = core.T
parse_txt = core.parse_txt

def empty():
    empty = core.XBunch()
    empty.nshandler = nshandling.get_nshandler_for_lang('de')
    return empty

def test_parse_row_missing_beginrow():
    tokens = tokenize("<td>implicit row starts here</td><td>cell2</td>")
    core.parse_table_rows(tokens, empty())
    show(tokens)
    assert len(tokens)==1
    assert tokens[0].type == T.t_complex_table_row
    assert [x.type for x in tokens[0].children] == [T.t_complex_table_cell]*2
    

def test_parse_table_cells_missing_close():
    tokens = core.tokenize("<td>bla")
    core.parse_table_cells(tokens, empty())
    show(tokens)
    assert tokens[0].type==T.t_complex_table_cell, "expected a complex table cell"


def test_parse_table_cells_closed_by_next_cell():
    tokens = core.tokenize("<td>foo<td>bar")
    core.parse_table_cells(tokens, empty())
    show(tokens)
    assert tokens[0].type==T.t_complex_table_cell
    assert tokens[1].type==T.t_complex_table_cell

    assert len(tokens[0].children)==1
    assert tokens[0].children[0]
    
def test_parse_table_cells_pipe():
    tokens = tokenize("{|\n|cell0||cell1||cell2\n|}")[2:-2]
    print "BEFORE:"
    show(tokens)
    core.parse_table_cells(tokens, empty())
    print "AFTER"
    show(tokens)
    assert len(tokens)==3
    
    for i, x in enumerate(tokens):
        print "cell", i
        assert x.type==T.t_complex_table_cell, "cell %s bad" % (i,)
        assert len(x.children)==1, "cell %s has wrong number of children" % (i,)
        assert x.children[0].type==T.t_text
        assert x.children[0].text==('cell%s' % i)

def test_parse_cell_modifier():
    tokens = tokenize("""{|
|align="right"|cell0|still_cell0
|}""")[2:-2]
    
    print "BEFORE:"
    show(tokens)
    core.parse_table_cells(tokens, empty())
    print "AFTER"
    show(tokens)
    assert tokens[0].type == T.t_complex_table_cell
    assert tokens[0].vlist == dict(align="right")
    assert T.join_as_text(tokens[0].children)=="cell0|still_cell0"
    
def test_parse_table_modifier():
    tokens = tokenize("""{| border="1"
|}
""")
    
    print "BEFORE:"
    show(tokens)
    core.parse_tables(tokens, empty())
    
    print "AFTER:"
    show(tokens)

    assert tokens[0].type==T.t_complex_table
    assert tokens[0].vlist == dict(border=1)


def test_parse_table_row_modifier():
    tokens = tokenize("""{|
|- style="background:red; color:white"
| cell
|}
""")[2:-2]
    
    print "BEFORE:"
    show(tokens)
    core.parse_table_rows(tokens, empty())
    
    print "AFTER:"
    show(tokens)

    assert tokens[0].vlist
    

def test_parse_link():
    tokens = tokenize("[[link0]][[link2]]")
    core.parse_links(tokens, empty())
    show(tokens)
    assert len(tokens)==2
    assert tokens[0].type == T.t_complex_link
    assert tokens[1].type == T.t_complex_link

def test_no_row_modifier():    
    s="{|\n|foo||bar\n|}"
    r=core.parse_txt(s)
    core.show(r)
    cells = list(core.walknode(r, lambda x: x.type==core.T.t_complex_table_cell))
    print "CELLS:", cells
    assert len(cells)==2, "expected 2 cells"
    
def test_parse_para_vs_preformatted():
    s=' foo\n\nbar\n'
    r=core.parse_txt(s)
    core.show(r)
    pre = list(core.walknode(r, lambda x: x.type==core.T.t_complex_preformatted))[0]
    core.show(pre)
    textnodes = list(core.walknode(pre, lambda x: x.type==core.T.t_text))
    txt=''.join([x.text for x in textnodes])
    assert u'bar' not in txt
               
def test_duplicate_nesting():
    s=u"""<b>
[[foo|bar]] between
</b>"""
    r = core.parse_txt(s)
    bolds = list(core.walknode(r, lambda x: x.tagname=="b"))
    core.show(bolds)
    
    for x in bolds:
        for y in x.children or []:
            assert y.tagname != "b"

def test_ref_no_newline():
    s=u"""<ref>* no item</ref>"""
    r = core.parse_txt(s)
    core.show(r)
    linodes = list(core.walknode(r, lambda x: x.tagname=="li"))
    assert not linodes

def test_tab_table():
    s="""
\t{|
|-
\t| cell1
| cell2
\t|}after
"""
    r = core.parse_txt(s)
    core.show(r)
    tables = []
    
    def allowed(node):
        retval = bool(tables)
        if node.type == T.t_complex_table:
            tables.append(node)
        return retval
    nodes = [x for x in r if allowed(x)]
    assert nodes, "bad  or no table"

    cells = core.walknodel(r, lambda x: x.type==T.t_complex_table_cell)
    assert len(cells)==2, "expected two cells"

def test_parse_ul_not_preformatted():
    """http://code.pediapress.com/wiki/ticket/554"""
    s="""
<ul>
   <li>bla blub
   <li>bla bla
 </ul>
"""
    r=parse_txt(s)
    core.show(r)
    pre = core.walknodel(r, lambda x: x.type==T.t_complex_preformatted)
    assert not pre, "should contain no preformatted nodes"



def test_link_vs_center():
    """http://code.pediapress.com/wiki/ticket/559"""
    s="""[[foo|bar <center> not closed]]"""
    r=parse_txt(s)
    core.show(r)
    assert r[0].type==T.t_complex_link, "expected a link"
    
def test_no_combine_dd_dt():
    """http://code.pediapress.com/wiki/ticket/549"""
    def doit(s):
        r=parse_txt(s)
        core.show(r)
        styles = core.walknodel(r, lambda x: x.type==T.t_complex_style)
        print styles
        assert len(styles)==2

        
    yield doit, ":first\n:second\n"
    yield doit, ";first\n;second\n"

def test_combine_preformatted():
    """http://code.pediapress.com/wiki/ticket/569"""
    s = " preformatted\n and more preformatted\n"
    r=parse_txt(s)
    core.show(r)
    pre = core.walknodel(r, lambda x: x.type==T.t_complex_preformatted)
    assert len(pre)==1, "expected exactly one preformatted node"

def test_bad_section():
    """http://code.pediapress.com/wiki/ticket/588"""
    s = """<div>
div ends here
== this is </div> a section title ==
some text
"""
    r=parse_txt(s)
    show(r)
    
def test_mark_style_595():
    """http://code.pediapress.com/wiki/ticket/595"""
    r = parse_txt( '<b><i>[[Article link|Display text]]</i></b> after')
    b = core.walknodel(r, lambda x: x.tagname=="b")
    print b
    assert len(b)==1, "expected exactly one bold node"

def test_unexpected_end():
    """http://code.pediapress.com/wiki/ticket/607"""
    parse_txt("{|")

def test_link_in_table_caption():
    """http://code.pediapress.com/wiki/ticket/578"""
    s="""{| 
|+ id="CFNP" [[bla | blubb]]
|-
| a || b
|}
"""
    r =  parse_txt(s)
    with_vlist =  core.walknodel(r, lambda x: bool(x.vlist))
    print with_vlist
    
    assert not with_vlist,  "no node should contain a vlist"

def test_html_entity_in_pre():
    r = parse_txt("<pre>&gt;</pre>")
    txt = r[0].children[0].text
    print txt
    assert txt == ">",  "wrong text"
    
def test_nowiki_in_pre():
    """http://code.pediapress.com/wiki/ticket/617"""
    r = parse_txt("<pre><nowiki>foo</nowiki></pre>")
    txt = r[0].children[0].text
    print txt
    assert txt == "foo",  "wrong text"

def test_s_tag():
    r = parse_txt("<s>strike</s>")
    s = core.walknodel(r, lambda x: x.tagname == "s")
    assert len(s) == 1
    
def test_var_tag():
    r = parse_txt("<var>strike</var>")
    s = core.walknodel(r, lambda x: x.tagname == "var")
    assert len(s) == 1

def test_empty_link():
    """http://code.pediapress.com/wiki/ticket/621"""
    r = parse_txt("[[de:]]")
    print r
    assert r[0].type == T.t_complex_link



def test_source():
    r = parse_txt("foo <source>bar</source> baz")
    show(r)
    assert r[0].tagname=="p"
    assert r[1].tagname=="source"
    assert r[1].blocknode==True
    assert r[2].tagname=="p"
    
def test_source_enclose():
    r = parse_txt('foo <source enclose="none">bar</source> baz')
    show(r)
    assert r[0].type==T.t_text
    assert r[1].tagname=="source"
    assert r[1].blocknode==False
    assert r[2].type==T.t_text

@xfail
def test_urllink_in_link():
    """http://code.pediapress.com/wiki/ticket/602"""
    r = parse_txt("[[foo|[http://baz.com baz]]]")
    li = core.walknodel(r, lambda x: x.type==T.t_complex_link)
    assert len(li)==1,  "expected one link"
    nu = core.walknodel(r, lambda x: x.type==T.t_complex_named_url)
    show(r)
    assert len(nu)==1, "expected exactly one named url"
    
@xfail
def test_urllink_in_brackets():
    """http://code.pediapress.com/wiki/ticket/556"""
    r = parse_txt("[[http://example.com bla]]")
    show(r)
    nu = core.walknodel(r, lambda x: x.type==T.t_complex_named_url)
    print nu
    assert len(nu)==1,  "expected exactly one named url"

def test_lines_with_table_space():
    parse_txt("""* foo
 :{|
 |-
 | bar
 | baz
 |}
""")

def test_sub_close_sup():
    """http://code.pediapress.com/wiki/ticket/634"""
    r=parse_txt("<sup>foo</sub>bar")
    show(r)
    assert "bar" not in T.join_as_text(r[0].children), "bar should not be inside sup tag"
    
def test_sup_close_sub():
    """http://code.pediapress.com/wiki/ticket/634"""
    r=parse_txt("<sub>foo</sup>bar")
    show(r)
    assert "bar" not in T.join_as_text(r[0].children), "bar should not be inside sub tag"
    

def test_dd_dt_tags_inside_table():
    r=parse_txt("""{|
|-
| blubb <dl> bla <dt>foobazbar</dt>
|}
<dl> bla <dt>foobazbar</dt>
""")
    show(r)
    #assert 0 # FIXME

def test_left_to_right_mark():
    def doit(s):
        r=parse_txt(s)
        show(r)
        target = r[0].target
        assert target=="Image:foo.jpg", "wrong target"
        
    for mark in (u"\u200e", u"\u200f"):
        s=u"[[Image:foo.jpg" + mark + "|thumb|foobar]]"
        yield doit, s

def test_image_blocknode():
    
    def blocknode(s):
        r=parse_txt(s)[0]
        assert r.blocknode
        
    def noblocknode(s):
        r=parse_txt(s)[0]
        assert not r.blocknode

    yield noblocknode, "[[Image:foo.png]]"
    yield noblocknode, "[[Image:foo.png|150px]]"
    yield noblocknode, "[[Image:foo.png|frameless]]"
    
    yield blocknode, "[[Image:foo.png|left]]"
    yield blocknode, "[[Image:foo.png|thumb]]"
    yield blocknode, "[[Image:foo.png|frame]]"

def test_no_preformatted_inside_li():
    """stupid: http://code.pediapress.com/wiki/ticket/676"""
    r = parse_txt("""<ol><li>in li:
  foo
  bar
</li></ol>
""")
    core.show(r)
    pre = core.walknodel(r, lambda x: x.type==T.t_complex_preformatted)
    assert not pre,  "should not contain preformatted"
    
    

def test_preformatted_empty_line():
    r=parse_txt("foo\n  pre1\n  \n  pre2\nbar\n")
    core.show(r)
    pre = core.walknodel(r, lambda x: x.type==T.t_complex_preformatted)
    assert len(pre)==1, "expected exactly one preformatted node"

def test_inputbox():  
    s= "</inputbox>"
    
    r = core.parse_txt(s)
    core.show(r)
    
def test_ref_inside_caption():
    s="""
{|
|+ table capshun <ref>references fun</ref>
| hey || ho
|}"""
    r=core.parse_txt(s)
    core.show(r)
    cap = core.walknodel(r, lambda x:x.type==T.t_complex_caption)[0]
    print "caption:"
    core.show(cap)
    refs= core.walknodel(cap, lambda x: x.tagname=="ref")
    assert refs
    
def test_tr_inside_caption():
    """http://code.pediapress.com/wiki/ticket/709"""
    s="""
{|
|+ table capshun <tr><td>bla</td></tr>
|}"""
    r=core.parse_txt(s)
    core.show(r)
    cap = core.walknodel(r, lambda x:x.type==T.t_complex_caption)[0]
    print "caption:"
    core.show(cap)

    rows = core.walknodel(r, lambda x: x.type==T.t_complex_table_row)
    print "ROWS:",  rows
    assert len(rows)==1,  "no rows found"

    rows = core.walknodel(cap, lambda x: x.type==T.t_complex_table_row)
    print "ROWS:",  rows
    assert len(rows)==0, "row in table caption found"
