#! /usr/bin/env py.test

from mwlib.refine import core
from mwlib import nshandling

tokenize = core.tokenize
show = core.show
T = core.T
parse_txt = core.parse_txt
empty = core.XBunch()
empty.nshandler = nshandling.get_nshandler_for_lang('de')



def test_parse_row_missing_beginrow():
    tokens = tokenize("<td>implicit row starts here</td><td>cell2</td>")
    core.parse_table_rows(tokens, empty)
    show(tokens)
    assert len(tokens)==1
    assert tokens[0].type == T.t_complex_table_row
    assert [x.type for x in tokens[0].children] == [T.t_complex_table_cell]*2
    

def test_parse_table_cells_missing_close():
    tokens = core.tokenize("<td>bla")
    core.parse_table_cells(tokens, empty)
    show(tokens)
    assert tokens[0].type==T.t_complex_table_cell, "expected a complex table cell"


def test_parse_table_cells_closed_by_next_cell():
    tokens = core.tokenize("<td>foo<td>bar")
    core.parse_table_cells(tokens, empty)
    show(tokens)
    assert tokens[0].type==T.t_complex_table_cell
    assert tokens[1].type==T.t_complex_table_cell

    assert len(tokens[0].children)==1
    assert tokens[0].children[0]
    
def test_parse_table_cells_pipe():
    tokens = tokenize("{|\n|cell0||cell1||cell2\n|}")[2:-2]
    print "BEFORE:"
    show(tokens)
    core.parse_table_cells(tokens, empty)
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
    core.parse_table_cells(tokens, empty)
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
    core.parse_tables(tokens, empty)
    
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
    core.parse_table_rows(tokens, empty)
    
    print "AFTER:"
    show(tokens)

    assert tokens[0].vlist
    

def test_parse_link():
    tokens = tokenize("[[link0]][[link2]]")
    refined = []
    core.parse_links(tokens, empty)
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
    
