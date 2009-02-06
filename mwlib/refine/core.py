#! /usr/bin/env python

import sys
from mwlib.utoken import tokenize, show, token as T
from mwlib.refine import util
from mwlib import namespace

try:
    from blist import blist
except ImportError:
    import warnings
    warnings.warn("using normal list. parsing might be slower. please run 'easy_install blist'")
    blist = list

T.t_complex_table = "complex_table"
T.t_complex_caption = "complex_caption"
T.t_complex_table_row = "complex_table_row"
T.t_complex_table_cell = "complex_table_cell"
T.t_complex_tag = "complex_tag"
T.t_complex_link = "link"
T.t_complex_section = "section"
T.t_complex_article = "article"
T.t_vlist = "vlist"

T.children = None


def get_recursive_tag_parser(tagname, break_at=None):
    if break_at is None:
        break_at = lambda _: False
        
    def recursive_parse_tag(tokens, refined):            
        i = 0
        stack = []
        while i<len(tokens):
            t = tokens[i]
            if stack and break_at(t):
                start = stack.pop()
                sub = tokens[start+1:i]
                tokens[start:i] = [T(type=T.t_complex_tag, start=0, len=0, children=sub, tagname=tagname)]
                refined.append(tokens[start])
                i=start+1
            elif t.type==T.t_html_tag and t.tagname==tagname:
                stack.append(i)
                i+=1
            elif t.type==T.t_html_tag_end and t.tagname==tagname:
                if stack:
                    start = stack.pop()
                    sub = tokens[start+1:i]
                    tokens[start:i+1] = [T(type=T.t_complex_tag, start=tokens[start].start, len=4, children=sub, tagname=tagname)]
                    refined.append(tokens[start])
                    i = start+1
                else:
                    i+=1
            else:
                i+= 1

        while stack:
            start = stack.pop()
            sub = tokens[start+1:]
            tokens[start:] = [T(type=T.t_complex_tag, start=tokens[start].start, len=4, children=sub, tagname=tagname)]
            refined.append(tokens[start])

        refined.append(tokens)
    recursive_parse_tag.__name__ += "_"+tagname
    
    return recursive_parse_tag

parse_div = get_recursive_tag_parser("div")

def _li_break_at(token):
    if token.type==T.t_html_tag and token.tagname=="li":
        return True
    return False
                      
parse_li = get_recursive_tag_parser("li", _li_break_at)
parse_ol = get_recursive_tag_parser("ol")
parse_ul = get_recursive_tag_parser("ul")
parse_span = get_recursive_tag_parser("span")
parse_p = get_recursive_tag_parser("p")

class bunch(object):
    def __init__(self, **kw):
        self.__dict__.update(kw)
        
class parse_sections(object):
    def __init__(self, tokens, refined):
        self.tokens = tokens
        self.refined = refined
        self.run()
        
    def run(self):
        tokens = self.tokens
        i = 0

        sections = []
        current = bunch(start=None, end=None, endtitle=None)

        def create():
            l1 = tokens[current.start].text.count("=")
            l2 = tokens[current.endtitle].text.count("=")
            level = min (l1, l2)
            # FIXME add = when l1!=l2
            
            caption = T(type=T.t_complex_caption, start=0, len=0, children=tokens[current.start+1:current.endtitle])
            sub = blist([caption])
            sub.extend(tokens[current.endtitle+1:i])
            sect = T(type=T.t_complex_section, start=0, len=0, children=sub, level=level)
            tokens[current.start:i] = [sect] 
            
            self.refined.append(tokens[current.start])

            while sections and level<sections[-1].level:
                sections.pop()
            if sections and level>sections[-1].level:
                sections[-1].children.append(tokens[current.start])
                del tokens[current.start]
                current.start -= 1

            sections.append(sect)
            
        while i<len(self.tokens):
            t = tokens[i]
            if t.type==T.t_section:
                if current.endtitle is not None:
                    create()                    
                    i = current.start+1
                    current = bunch(start=None, end=None, endtitle=None)
                else:
                    current.start = i
                    i += 1
            elif t.type==T.t_section_end:
                current.endtitle = i
                i+= 1
            else:
                i+=1

        if current.endtitle is not None:
            create()
        self.refined.append(tokens)
        
                    
class parse_links(object):
    def __init__(self, tokens, refined):
        self.tokens = tokens
        self.refined = refined
        self.run()

    def handle_image_modifier(self, mod, node):
        mod = mod.strip().lower()
        if mod=='thumb' or mod=='thumbnail':
            node.thumb = True
            return True
        
        if mod in ('left', 'right', 'center', 'none'):
            node.align = mod
            return True
        
        if mod in ('frame', 'framed', 'enframed', 'frameless'):
            node.frame = mod
            return True
        
        if mod=='border':
            node.border = True
            return True

        if mod.startswith('print='):
            node.printargs = mod[len('print='):]

        if mod.startswith('alt='):
            node.alt = mod[len('alt='):]

        if mod.startswith('link='):
            node.link = mod[len('link='):]

        if mod.endswith('px'):
                # x200px
                # 100x200px
                # 200px
                mod = mod[:-2]
                width, height = (mod.split('x')+['0'])[:2]
                try:
                    width = int(width)
                except ValueError:
                    width = 0

                try:
                    height = int(height)
                except ValueError:
                    height = 0

                node.width = width
                node.height = height
                return True
        return False
    
    def extract_image_modifiers(self, marks, node):
        cap = None
        for i in range(1,len(marks)-1):
            tmp = self.tokens[marks[i]+1:marks[i+1]]
            if not self.handle_image_modifier(T.join_as_text(tmp), node):
                cap = tmp
        return cap
        
        
    def run(self):
        tokens = self.tokens
        i = 0
        marks = []

        stack = []
        
        
        while i<len(self.tokens):
            t = tokens[i]
            if t.type==T.t_2box_open:
                if len(marks)>1:
                    stack.append(marks)
                marks = [i]
                i+=1
            elif t.type==T.t_special and t.text=="|":
                marks.append(i)
                i+=1
            elif t.type==T.t_2box_close and marks:
                marks.append(i)
                start = marks[0]
                
                target = T.join_as_text(tokens[start+1:marks[1]]).strip()
                if not target:
                    i+=1
                    if stack:
                        marks=stack.pop()
                    else:
                        marks=[]                        
                    continue
                else:
                    # FIXME: parse image modifiers: thumb, frame, ...
                    ns, partial, full = namespace.splitname(target)

                    
                    if ns==namespace.NS_MAIN:
                        # FIXME: could be an interwiki/language link. -> set ns=None
                        pass
                    
                    node = T(type=T.t_complex_link, start=0, len=0, children=blist(), ns=ns)

                    sub = None
                    if ns==namespace.NS_IMAGE:
                        sub = self.extract_image_modifiers(marks, node)                        
                    elif len(marks)>2:
                        sub = tokens[marks[1]+1:marks[-1]]

                    if sub is None:
                        sub = [T(type=T.t_text, start=0, len=0, text=target)]
                        
                    node.children = sub
                    tokens[start:i+1] = [node]
                    node.target = target
                    self.refined.append(sub)
                    if stack:
                        marks = stack.pop()
                    else:
                        marks = []
                    i = start+1
            else:
                i+=1

        self.refined.append(tokens)
        
class parse_table_cells(object):
    def __init__(self, tokens, refined):
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
    
    def run(self):
        tokens = self.tokens
        i = 0
        start = None

        while i < len(tokens):

            if self.is_table_cell_start(tokens[i]):
                if start is not None:

                    search_modifier = tokens[start].text in ("|", "!", "||")
                    sub = tokens[start+1:i]
                    tokens[start:i] = [T(type=T.t_complex_table_cell, start=tokens[start].start, len=4, children=sub)]
                    if search_modifier:
                        self.find_modifier(tokens[start])
                    self.refined.append(tokens[start])
                        
                    start += 1
                    i = start+1
                else:
                    start = i
                    i+=1
            elif self.is_table_cell_end(tokens[i]):
                if start is not None:
                    sub = tokens[start+1:i]
                    search_modifier = tokens[start].text in ("|", "!", "||")
                    tokens[start:i+1] = [T(type=T.t_complex_table_cell, start=tokens[start].start, len=4, children=sub)]
                    
                    if search_modifier:
                        self.find_modifier(tokens[start])
                    self.refined.append(tokens[start])
                    
                    i = start+1
                    start = None
                else:
                    i+= 1
            else:
                i += 1

        if start is not None:
            
            search_modifier = tokens[start].text in ("|", "!", "||")
            sub = tokens[start+1:]
            tokens[start:] = [T(type=T.t_complex_table_cell, start=tokens[start].start, len=4, children=sub)]
            
            if search_modifier:
                self.find_modifier(tokens[start])
            self.refined.append(tokens[start])
            
                
class parse_table_rows(object):
    def __init__(self, tokens, refined):
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
        
        while i < len(tokens):
            if start is None and self.is_table_cell_start(tokens[i]):
                start = i
                remove_start = 0                
            elif self.is_table_row_start(tokens[i]):
                if start is not None:
                    children = tokens[start+remove_start:i]
                    tokens[start:i] = [T(type=T.t_complex_table_row, start=tokens[start].start, len=4, children=children)]
                    self.find_modifier(tokens[start])
                    parse_table_cells(children, self.refined)
                    start += 1  # we didn't remove the start symbol above
                    remove_start = 1
                    i = start+1
                else:
                    remove_start = 1
                    start = i
                    i+=1
            elif self.is_table_row_end(tokens[i]):
                if start is not None:
                    sub = tokens[start+remove_start:i]
                    tokens[start:i+1] = [T(type=T.t_complex_table_row, start=tokens[start].start, len=4, children=sub)]
                    self.find_modifier(tokens[start])
                    parse_table_cells(sub, self.refined)
                    i = start+1
                    start = None
                else:
                    i+= 1
            else:
                i += 1

        if start is not None:
            sub = tokens[start+remove_start:]
            tokens[start:] = [T(type=T.t_complex_table_row, start=tokens[start].start, len=4, children=sub)]
            self.find_modifier(tokens[start])
            parse_table_cells(sub, self.refined)
        
class parse_tables(object):
    def __init__(self, tokens, refined):
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
        for i,x in enumerate(children):
            if x.type in (T.t_newline, T.t_break):
                mod = T.join_as_text(children[:i])
                #print "MODIFIER:", repr(mod)
                table.vlist = util.parseParams(mod)
                del children[:i]
                return

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

        while i < len(tokens):
            if self.is_table_start(tokens[i]):
                stack.append(i)
                i+=1
            elif self.is_table_end(tokens[i]):
                if stack:
                    start = stack.pop()
                    starttoken = tokens[start]
                    
                    sub = tokens[start+1:i]
                    tokens[start:i+1] = [T(type=T.t_complex_table, start=tokens[start].start, len=4, children=sub)]
                    if starttoken.text == "{|":
                        self.find_modifier(tokens[start])
                    self.handle_rows(sub)
                    self.find_caption(tokens[start])
                    
                    i = start+1
                else:
                    i += 1
            else:
                i += 1

        while stack:
            start = stack.pop()
            starttoken = tokens[start]
            sub = tokens[start+1:]
            tokens[start:] = [T(type=T.t_complex_table, start=tokens[start].start, len=4, children=sub)]
            if starttoken.text == "{|":
                self.find_modifier(tokens[start])
            self.handle_rows(sub)
            self.find_caption(tokens[start])

            
def parse_txt(txt):
    tokens = blist(tokenize(txt))

    refine = [tokens]
    parsers = [parse_span, parse_li, parse_p, parse_ul, parse_ol, parse_links, parse_sections, parse_div, parse_tables]
    while parsers:
        p = parsers.pop()
        #print "doing", p, "on:", refine
        
        next = []
        
        for x in refine:
            if isinstance(x, (list, blist, tuple)):
                toks = x
            else:
                toks = x.children
            #print "BEFORE:", p, toks
            p(toks, next)
            #print "AFTER:", toks

        refine = next
        
    return tokens
