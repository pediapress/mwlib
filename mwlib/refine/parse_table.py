
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.txt for additional licensing information.

from mwlib.utoken import show, token as T
from mwlib.refine import util

class parse_table_cells(object):
    def __init__(self, tokens, refined, **kwargs):
        self.tokens = tokens
        self.refined = refined
        self.run()
        
    def is_table_cell_start(self, token):
        return token.type==T.t_column or (token.type==T.t_html_tag and token.tagname in ("td", "th"))

    def is_table_cell_end(self, token):
        return token.type==T.t_html_tag_end and token.tagname in ("td", "th")

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

        def makecell(skip_end=0):
            search_modifier = tokens[start].text.strip() in ("|", "!", "||")
            sub = tokens[start+1:i-skip_end]
            self.replace_tablecaption(sub)
            tokens[start:i] = [T(type=T.t_complex_table_cell, start=tokens[start].start, len=4, children=sub, vlist=tokens[start].vlist)]
            if search_modifier:
                self.find_modifier(tokens[start])
            self.refined.append(tokens[start])
        
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
    def __init__(self, tokens, refined, **kwargs):
        self.tokens = tokens
        self.refined = refined
        self.run()
        
    def is_table_row_start(self, token):
        return token.type==T.t_row or (token.type==T.t_html_tag and token.tagname=='tr')

    def is_table_row_end(self, token):
        return token.type==T.t_html_tag_end and token.tagname=='tr'
    
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
        return token.type==T.t_column or (token.type==T.t_html_tag and token.tagname in ("td", "th"))
    
    def run(self):
        tokens = self.tokens
        i = 0

        start = None
        remove_start = 1
        vlist = None
        rowbegintoken = None
        def should_find_modifier():
            if rowbegintoken is None:
                return False
            if rowbegintoken.tagname:
                return False
            return True

        def args():
            if rowbegintoken is None:
                return {}
            return dict(vlist=rowbegintoken.vlist, tagname=rowbegintoken.tagname)
        
            
        while i < len(tokens):
            if start is None and self.is_table_cell_start(tokens[i]):
                rowbegintoken = None
                start = i
                remove_start = 0
                i+=1
            elif self.is_table_row_start(tokens[i]):
                if start is not None:
                    children = tokens[start+remove_start:i]
                    tokens[start:i] = [T(type=T.t_complex_table_row, start=tokens[start].start, len=4, children=children, **args())]
                    if should_find_modifier():
                        self.find_modifier(tokens[start])
                    parse_table_cells(children, self.refined)
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
                    tokens[start:i+1] = [T(type=T.t_complex_table_row, start=tokens[start].start, len=4, children=sub, **args())]
                    if should_find_modifier():
                        self.find_modifier(tokens[start])
                    parse_table_cells(sub, self.refined)
                    i = start+1
                    start = None
                    rowbegintoken = None
                else:
                    i+= 1
            else:
                i += 1

        if start is not None:
            sub = tokens[start+remove_start:]
            tokens[start:] = [T(type=T.t_complex_table_row, start=tokens[start].start, len=4, children=sub, **args())]
            if should_find_modifier():
                self.find_modifier(tokens[start])
            parse_table_cells(sub, self.refined)
        
class parse_tables(object):
    def __init__(self, tokens, refined, **kwargs):
        self.tokens = tokens
        self.refined = refined
        self.run()
        
    def is_table_start(self, token):
        return token.type==T.t_begintable or (token.type==T.t_html_tag and token.tagname=="table")

    def is_table_end(self, token):
        return token.type==T.t_endtable or (token.type==T.t_html_tag_end and token.tagname=="table")

    def handle_rows(self, sublist):
        parse_table_rows(sublist, self.refined)

    def find_modifier(self, table):
        children = table.children
        def compute_mod():
            mod = T.join_as_text(children[:i])
            #print "MODIFIER:", repr(mod)
            table.vlist = util.parseParams(mod)
            del children[:i]

            
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

        while i<len(children):
            t = children[i]
            if t.text is None or t.text.startswith("\n"):
                sub = children[start+1:i]
                caption = T(type=T.t_complex_caption, start=0, len=0, children=sub)
                children[start:i] = [caption]
                return
            i += 1
            
    def run(self):
        tokens = self.tokens
        self.refined.append(tokens)
        i = 0
        stack = []

        def maketable():
            start = stack.pop()
            starttoken = tokens[start]
            sub = tokens[start+1:i]
            tokens[start:i+1] = [T(type=T.t_complex_table, start=tokens[start].start, len=4, children=sub, vlist=starttoken.vlist)]
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
        
