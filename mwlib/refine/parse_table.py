# -*- compile-command: "../../tests/test_refine.py" -*-

# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

from mwlib.utoken import show, token as T
from mwlib.refine import util

class parse_table_cells(object):
    def __init__(self, tokens, xopts):
        self.tokens = tokens
        self.run()
        
    def is_table_cell_start(self, token):
        return token.type==T.t_column or (token.type==T.t_html_tag and token.rawtagname in ("td", "th"))

    def is_table_cell_end(self, token):
        return token.type==T.t_html_tag_end and token.rawtagname in ("td", "th")

    def find_modifier(self, cell):
        children = cell.children
        if not children:
            return
        for i,x in enumerate(children):
            t = children[i]
            if t.type==T.t_2box_open:
                break
            if t.type==T.t_special and t.text=="|":
                mod = T.join_as_text(children[:i])
                cell.vlist = util.parseParams(mod)
                
                del children[:i+1]
                return

    def replace_tablecaption(self, children):
        i = 0
        while i<len(children):
            if children[i].type == T.t_tablecaption:
                children[i].type = T.t_special
                children[i].text = u"|"
                children.insert(i+1, T(type=T.t_text, text="+"))
            i+=1
            
                
                
    def run(self):
        tokens = self.tokens
        i = 0
        start = None
        self.is_header = False
        
        def makecell(skip_end=0):
            st = tokens[start].text.strip()
            if st=="|":
                self.is_header = False
            elif st=="!":
                self.is_header = True
            is_header = self.is_header
            
            if tokens[start].rawtagname=="th":
                is_header = True
            elif tokens[start].rawtagname=="td":
                is_header = False

            if is_header:
                tagname = "th"
            else:
                tagname = "td"
                
                
            search_modifier = tokens[start].text.strip() in ("|", "!", "||", "!!")
            sub = tokens[start+1:i-skip_end]
            self.replace_tablecaption(sub)
            tokens[start:i] = [T(type=T.t_complex_table_cell, tagname=tagname,
                                 start=tokens[start].start, children=sub,
                                 vlist=tokens[start].vlist, is_header=is_header)]
            if search_modifier:
                self.find_modifier(tokens[start])
        
        while i < len(tokens):
            if self.is_table_cell_start(tokens[i]):
                if start is not None:
                    makecell()                        
                    start += 1
                    i = start+1
                else:
                    start = i
                    i+=1
                        
            elif self.is_table_cell_end(tokens[i]):
                if start is not None:
                    i+=1
                    makecell(skip_end=1)                    
                    i = start+1
                    start = None
                else:
                    i+= 1
            else:
                i += 1

        if start is not None:
            makecell()
            
                
class parse_table_rows(object):
    def __init__(self, tokens, xopts):
        self.tokens = tokens
        self.xopts = xopts
        self.run()
        
    def is_table_row_start(self, token):
        return token.type==T.t_row or (token.type==T.t_html_tag and token.rawtagname=='tr')

    def is_table_row_end(self, token):
        return token.type==T.t_html_tag_end and token.rawtagname=='tr'
    
    def find_modifier(self, row):
        children = row.children
        for i,x in enumerate(children):
            if x.type in (T.t_newline, T.t_break):
                mod = T.join_as_text(children[:i])
                #print "MODIFIER:", repr(mod)
                row.vlist = util.parseParams(mod)
                del children[:i]
                return
            
    def is_table_cell_start(self, token):
        return token.type==T.t_column or (token.type==T.t_html_tag and token.rawtagname in ("td", "th"))
    
    def run(self):
        tokens = self.tokens
        i = 0

        start = None
        remove_start = 1
        rowbegintoken = None
        def should_find_modifier():
            if rowbegintoken is None:
                return False
            if rowbegintoken.rawtagname:
                return False
            return True

        def args():
            if rowbegintoken is None:
                return {}
            return dict(vlist=rowbegintoken.vlist)
        
            
        while i < len(tokens):
            if start is None and self.is_table_cell_start(tokens[i]):
                rowbegintoken = None
                start = i
                remove_start = 0
                i+=1
            elif self.is_table_row_start(tokens[i]):
                if start is not None:
                    children = tokens[start+remove_start:i]
                    tokens[start:i] = [T(type=T.t_complex_table_row, tagname="tr", start=tokens[start].start, children=children, **args())]
                    if should_find_modifier():
                        self.find_modifier(tokens[start])
                    parse_table_cells(children, self.xopts)
                    start += 1  # we didn't remove the start symbol above
                    rowbegintoken= tokens[start]
                    remove_start = 1
                    i = start+1
                    
                else:
                    rowbegintoken = tokens[i]
                    remove_start = 1
                    start = i
                    i+=1
            elif self.is_table_row_end(tokens[i]):
                if start is not None:
                    sub = tokens[start+remove_start:i]
                    tokens[start:i+1] = [T(type=T.t_complex_table_row, tagname="tr", start=tokens[start].start, children=sub, **args())]
                    if should_find_modifier():
                        self.find_modifier(tokens[start])
                    parse_table_cells(sub, self.xopts)
                    i = start+1
                    start = None
                    rowbegintoken = None
                else:
                    i+= 1
            else:
                i += 1

        if start is not None:
            sub = tokens[start+remove_start:]
            tokens[start:] = [T(type=T.t_complex_table_row, tagname="tr", start=tokens[start].start, children=sub, **args())]
            if should_find_modifier():
                self.find_modifier(tokens[start])
            parse_table_cells(sub, self.xopts)
        
class parse_tables(object):
    def __init__(self, tokens, xopts):
        self.xopts = xopts
        self.tokens = tokens
        self.run()
        
    def is_table_start(self, token):
        return token.type==T.t_begintable or (token.type==T.t_html_tag and token.rawtagname=="table")

    def is_table_end(self, token):
        return token.type==T.t_endtable or (token.type==T.t_html_tag_end and token.rawtagname=="table")

    def handle_rows(self, sublist):
        parse_table_rows(sublist, self.xopts)

    def find_modifier(self, table):
        children = table.children
        def compute_mod():
            mod = T.join_as_text(children[:i])
            #print "MODIFIER:", repr(mod)
            table.vlist = util.parseParams(mod)
            del children[:i]

        i = 0    
        for i,x in enumerate(children):
            if x.type in (T.t_newline, T.t_break):
                break

        compute_mod()
        
    def find_caption(self, table):
        children = table.children
        start = None
        i = 0
        while i < len(children):
            t = children[i]
            if t.type==T.t_tablecaption:
                start = i
                i += 1
                break

            if t.text is None or t.text.strip():
                return
            i+=1

        modifier = None
        
        while i<len(children):
            t = children[i]
            if t.tagname not in ("ref",) and (t.text is None or t.text.startswith("\n")):
                if modifier:
                    mod = T.join_as_text(children[start:modifier])
                    vlist = util.parseParams(mod)
                    sub = children[modifier+1:i]
                else:
                    sub = children[start+1:i]
                    vlist = {}
                    
                caption = T(type=T.t_complex_caption, children=sub, vlist=vlist)
                children[start:i] = [caption]
                return
            elif t.text=="|" and modifier is None:
                modifier = i
            elif t.type == T.t_2box_open and modifier is None:
                modifier =  0
                
            i += 1
            
    def run(self):
        tokens = self.tokens
        i = 0
        stack = []

        def maketable():
            start = stack.pop()
            starttoken = tokens[start]
            sub = tokens[start+1:i]
            from mwlib.refine import core
            tp = core.tagparser()
            tp.add("caption", 5)
            tp(sub, self.xopts)
            tokens[start:i+1] = [T(type=T.t_complex_table,
                                   tagname="table", start=tokens[start].start, children=sub,
                                   vlist=starttoken.vlist, blocknode=True)]
            if starttoken.text.strip() == "{|":
                self.find_modifier(tokens[start])
            self.handle_rows(sub)
            self.find_caption(tokens[start])
            return start

            
        while i < len(tokens):
            if self.is_table_start(tokens[i]):
                stack.append(i)
                i+=1
            elif self.is_table_end(tokens[i]):
                if stack:
                    i = maketable()+1
                else:
                    i += 1
            else:
                i += 1

        while stack:
            maketable()
        
class fix_tables(object):
    def __init__(self, tokens, xopts):
        self.xopts = xopts
        self.tokens = tokens
        self.run()
        
    def run(self):
        tokens = self.tokens
        for x in tokens:
            if x.type != T.t_complex_table:
                continue

            rows = [c for c in x.children if c.type in (T.t_complex_table_row, T.t_complex_caption)]
            if not rows:
                x.type = T.t_complex_node
                x.tagname = None
                
def extract_garbage(tokens, is_allowed,  is_whitespace=None):
    if is_whitespace is None:
        is_whitespace = lambda t: t.type in (T.t_newline,  T.t_break)
        
    res = []
    i = 0
    start = None
    
    while i<len(tokens):
        if is_whitespace(tokens[i]):
            if start is None:
                start = i
            i+=1
        elif is_allowed(tokens[i]):
            start = None
            i+=1
        else:
            if start is None:
                start = i
            i+=1
            
            # find end of garbage
            
            while i<len(tokens):
                if is_allowed(tokens[i]):
                   break
                i+= 1
                
            garbage = tokens[start:i]
            del tokens[start:i]
            i = start
            res.append(T(type=T.t_complex_node, children=garbage))
            
    return res

class remove_table_garbage(object):
    need_walker = False
    
    def __init__(self, tokens, xopts):
        from mwlib.refine import core
        walker = core.get_token_walker()
        for t in walker(tokens):
            self.tokens = t
            self.run()
        
    def run(self):
        tokens = self.tokens
        tableidx = 0
        while tableidx<len(tokens):
            if tokens[tableidx].type==T.t_complex_table:
                # garbage = extract_garbage(tokens[tableidx].children,
                #                           is_allowed=lambda t: t.type in (T.t_complex_table_row, T.t_complex_caption))

                tmp = []
                for c in tokens[tableidx].children:
                    if c.type==T.t_complex_table_row:
                        rowgarbage = extract_garbage(c.children,
                                                     is_allowed=lambda t: t.type in (T.t_complex_table_cell, ))
                        tmp.extend(rowgarbage)
                        
                        
                tokens[tableidx+1:tableidx+1] = tmp
            tableidx+=1
