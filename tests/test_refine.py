#! /usr/bin/env py.test

import mwlib.refine.core as refine

tokenize = refine.tokenize
show = refine.show
T = refine.T



def test_parse_row_missing_beginrow():
    tokens = tokenize("<td>implicit row starts here</td><td>cell2</td>")
    refine.parse_table_rows(tokens, [])
    show(tokens)
    assert len(tokens)==1
    assert tokens[0].type == T.t_complex_table_row
    assert [x.type for x in tokens[0].children] == [T.t_complex_table_cell]*2
    

def test_parse_table_cells_missing_close():
    tokens = refine.tokenize("<td>bla")
    refine.parse_table_cells(tokens, [])
    show(tokens)
    assert tokens[0].type==T.t_complex_table_cell, "expected a complex table cell"


def test_parse_table_cells_closed_by_next_cell():
    tokens = refine.tokenize("<td>foo<td>bar")
    refine.parse_table_cells(tokens, [])
    show(tokens)
    assert tokens[0].type==T.t_complex_table_cell
    assert tokens[1].type==T.t_complex_table_cell

    assert len(tokens[0].children)==1
    assert tokens[0].children[0]
    
def test_parse_table_cells_pipe():
    tokens = tokenize("{|\n|cell0||cell1||cell2\n|}")[2:-2]
    print "BEFORE:"
    show(tokens)
    refine.parse_table_cells(tokens, [])
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
    refine.parse_table_cells(tokens, [])
    print "AFTER"
    show(tokens)
    assert tokens[0].type == T.t_complex_table_cell
    assert tokens[0].vlist == dict(align="right")
    assert T.join_as_text(tokens[0].children)=="cell0|still_cell0"



def test_parse_table_refined():
    tokens = tokenize("<table><tr><td>cell1</td></tr></table>")
    refined = []
    refine.parse_tables(tokens, refined)
    print "REFINED:", refined
    assert len(refined)==2
    

def test_parse_table_modifier():
    tokens = tokenize("""{| border="1"
|}
""")
    
    print "BEFORE:"
    show(tokens)
    refine.parse_tables(tokens, [])
    
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
    refine.parse_table_rows(tokens, [])
    
    print "AFTER:"
    show(tokens)

    assert tokens[0].vlist
    

def test_parse_link():
    tokens = tokenize("[[link0]][[link2]]")
    refined = []
    refine.parse_links(tokens, [])
    show(tokens)
    assert len(tokens)==2
    assert tokens[0].type == T.t_complex_link
    assert tokens[1].type == T.t_complex_link

def test_no_row_modifier():    
    s="{|\n|foo||bar\n|}"
    r=refine.parse_txt(s)
    refine.show(r)
    cells = list(refine.walknode(r, lambda x: x.type==refine.T.t_complex_table_cell))
    print "CELLS:", cells
    assert len(cells)==2, "expected 2 cells"
    
    
