#! /usr/bin/env python
# -*- compile-command: "../../tests/test_refine.py" -*-

# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

from mwlib.utoken import tokenize, show, token as T, walknode, walknodel
from mwlib.refine import util
from mwlib import tagext, uniq, nshandling

from mwlib.refine.parse_table import parse_tables, parse_table_cells, parse_table_rows, fix_tables, remove_table_garbage
from mwlib.refine.tagparser import tagparser

try:
    from mwlib.refine import _core
except ImportError:
    _core =  None

T.t_complex_table = "complex_table"
T.t_complex_caption = "complex_caption"
T.t_complex_table_row = "complex_table_row"
T.t_complex_table_cell = "complex_table_cell"
T.t_complex_tag = "complex_tag"
T.t_complex_link = "link"
T.t_complex_section = "section"
T.t_complex_article = "article"
T.t_complex_indent = "indent"
T.t_complex_line = "line"
T.t_complex_named_url = "named_url"
T.t_complex_style = "style"
T.t_complex_node = "node"
T.t_complex_preformatted = "preformatted"
T.t_complex_compat = "compat"

T.t_vlist = "vlist"

T.children = None

def get_token_walker(skip_tags=set()):
    def walk(tokens):
        res =  [tokens]
        todo = [tokens]
        
        while todo:
            for x in todo.pop():
                children = x.children
                if children:
                    todo.append(children)
                    if x.tagname not in skip_tags:
                        res.append(children)
        return res
    
    return walk

if _core is not None:
    get_token_walker = _core.token_walker
    

def get_recursive_tag_parser(tagname, blocknode=False):
    tp = tagparser()
    tp.add(tagname, 10, blocknode=blocknode)
    return tp
    
parse_div = get_recursive_tag_parser("div", blocknode=True)


def parse_inputbox(tokens, xopts):
    get_recursive_tag_parser("inputbox")(tokens, xopts)
    
    for t in tokens:
        if t.tagname=='inputbox':
            t.inputbox = T.join_as_text(t.children)
            del t.children[:]

def _parse_gallery_txt(txt, xopts):
    lines = [x.strip() for x in txt.split("\n")]
    sub = []
    for x in lines:
        if not x:
            continue

        assert xopts.expander is not None, "no expander in _parse_gallery_txt"
        xnew = xopts.expander.parseAndExpand(x, keep_uniq=True)

        linode = parse_txt(u'[['+xnew+']]', xopts)

        if linode:
            n = linode[0]
            if n.ns==nshandling.NS_IMAGE:
                sub.append(n)
                continue
        sub.append(T(type=T.t_text, text=xnew))
    return sub

class bunch(object):
    def __init__(self, **kw):
        self.__dict__.update(kw)
        
class parse_sections(object):
    def __init__(self, tokens, xopts):
        self.tokens = tokens
        self.run()
        
    def run(self):
        tokens = self.tokens
        i = 0

        sections = []
        current = bunch(start=None, end=None, endtitle=None)

        def create():
            if current.start is None or current.endtitle is None:
                return False
            
            l1 = tokens[current.start].text.count("=")
            l2 = tokens[current.endtitle].text.count("=")
            level = min (l1, l2)

            # FIXME: make this a caption
            caption = T(type=T.t_complex_node, children=tokens[current.start+1:current.endtitle]) 
            if l2>l1:
                caption.children.append(T(type=T.t_text, text=u"="*(l2-l1)))
            elif l1>l2:
                caption.children.insert(0, T(type=T.t_text, text=u"="*(l1-l2)))

            body = T(type=T.t_complex_node, children=tokens[current.endtitle+1:i])
              
            sect = T(type=T.t_complex_section, tagname="@section", children=[caption, body], level=level, blocknode=True)
            tokens[current.start:i] = [sect] 
            

            while sections and level<=sections[-1].level:
                sections.pop()
            if sections:
                sections[-1].children.append(tokens[current.start])
                del tokens[current.start]
                current.start -= 1

            sections.append(sect)
            return True


        
        while i<len(self.tokens):
            t = tokens[i]
            if t.type==T.t_section:
                if create():
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

        create()

class parse_urls(object):
    def __init__(self, tokens, xopts):
        self.tokens = tokens
        self.run()
        
    def run(self):
        tokens = self.tokens
        i=0
        start = None
        while i<len(tokens):
            t = tokens[i]
            
            if t.type==T.t_urllink and start is None:
                start = i
                i+=1
            elif t.type==T.t_special and t.text=="]" and start is not None:
                sub = self.tokens[start+1:i]
                self.tokens[start:i+1] = [T(type=T.t_complex_named_url, children=sub, caption=self.tokens[start].text[1:])]
                i = start
                start = None
            elif t.type==T.t_2box_close and start is not None:
                self.tokens[i].type = T.t_special
                self.tokens[i].text = "]"
                sub = self.tokens[start+1:i]
                self.tokens[start:i] = [T(type=T.t_complex_named_url, children=sub, caption=self.tokens[start].text[1:])]
                i = start
                start = None
            else:
                i+=1
                

class parse_singlequote(object):
    def __init__(self, tokens, xopts):
        self.tokens = tokens
        self.run()

    def run(self):
        def finish():
            assert len(counts)==len(styles)
            
            from mwlib.parser import styleanalyzer
            states = styleanalyzer.compute_path(counts)

            
            last_apocount = 0
            for i, s in enumerate(states):
                apos = "'"*(s.apocount-last_apocount)
                if apos:
                    styles[i].children.insert(0, T(type=T.t_text, text=apos))
                last_apocount = s.apocount

                if s.is_bold and s.is_italic:
                    styles[i].caption = "'''"
                    inner = T(type=T.t_complex_style, caption="''", children=styles[i].children)
                    styles[i].children = [inner]
                elif s.is_bold:
                    styles[i].caption = "'''"
                elif s.is_italic:
                    styles[i].caption = "''"
                else:
                    styles[i].type = T.t_complex_node
            
        
        tokens = self.tokens
        pos = 0
        start = None
        counts = []
        styles = []
        
        while pos<len(tokens):
            t = tokens[pos]
            if t.type==T.t_singlequote:
                if start is None:
                    counts.append(len(t.text))
                    start = pos
                    pos+=1
                else:
                    tokens[start:pos] = [T(type=T.t_complex_style, children=tokens[start+1:pos])]
                    styles.append(tokens[start])
                    pos = start+1
                    start = None
            elif t.type==T.t_newline:
                if start is not None:
                    tokens[start:pos] = [T(type=T.t_complex_style, children=tokens[start+1:pos])]
                    styles.append(tokens[start])
                    pos = start
                    start = None
                pos += 1
                
                if counts:
                    finish()
                    counts = []
                    styles = []
            else:
                pos += 1

        
        if start is not None:
            tokens[start:pos] = [T(type=T.t_complex_style, children=tokens[start+1:pos])]
            styles.append(tokens[start])
            
        if counts:
            finish()
                
                    
class parse_preformatted(object):
    need_walker = False
    def __init__(self, tokens, xopts):
        walker = get_token_walker(skip_tags=set(["table", "li", "tr", "@section"]))
        for t in walker(tokens):
            self.tokens = t
            self.run()

    def run(self):
        tokens = self.tokens
        i = 0
        start = None
        while i<len(tokens):
            t = tokens[i]
            if t.type==T.t_pre:
                assert start is None
                start = i
                i+=1
            elif t.type==T.t_newline and start is not None:
                sub = tokens[start+1:i+1]
                if start>0 and tokens[start-1].type==T.t_complex_preformatted:
                    del tokens[start:i+1]
                    tokens[start-1].children.extend(sub)
                    i = start
                else:    
                    tokens[start:i+1] = [T(type=T.t_complex_preformatted, children=sub, blocknode=True)]
                    i = start+1
                start = None
            elif t.blocknode or (t.type==T.t_complex_tag and t.tagname in ("blockquote", "table", "timeline", "div")):
                start = None
                i+=1
            else:
                i+=1
                
            
class parse_lines(object):
    def __init__(self, tokens, xopts):
        self.tokens = tokens
        self.run()

    def splitdl(self, item):
        for i, x in enumerate(item.children):
            if x.type==T.t_special and x.text==':':
                s=T(type=T.t_complex_style, caption=':', children=item.children[i+1:])
                del item.children[i:]
                return s
                 
    def analyze(self, lines):
        def getchar(node):
            assert node.type==T.t_complex_line
            if node.lineprefix:
                return node.lineprefix[0]
            return None
        
        
        lines.append(T(type=T.t_complex_line, lineprefix='<guard>')) # guard

        
        startpos = 0
        while startpos<len(lines)-1:
            prefix = getchar(lines[startpos])
            if prefix is None:
                if lines[startpos].tagname:
                    lines[startpos].type = T.t_complex_tag
                else:
                    lines[startpos].type = T.t_complex_node
                startpos+=1
                continue

            endtag = None
            if prefix==':':
                node = T(type=T.t_complex_style, caption=':')
                newitem = lambda: T(type=T.t_complex_node, blocknode=True)
            elif prefix=='*':
                node = T(type=T.t_complex_tag, tagname="ul")
                newitem = lambda: T(type=T.t_complex_tag, tagname="li", blocknode=True)
                endtag = "ul"
            elif prefix=="#":
                node = T(type=T.t_complex_tag, tagname="ol")
                newitem = lambda: T(type=T.t_complex_tag, tagname="li", blocknode=True)
                endtag = "ol"
            elif prefix==';':
                node = T(type=T.t_complex_style, caption=';')
                newitem = lambda: T(type=T.t_complex_node, blocknode=True)
            else:
                assert 0
                
            node.children = []
            dd = None

            def appendline():
                line = lines[startpos]
                if endtag:
                    for i, x in enumerate(line.children):
                        if x.rawtagname==endtag and x.type==T.t_html_tag_end:
                            after = line.children[i+1:]
                            del line.children[i:]
                            item.children.append(line)
                            lines[startpos] = T(type=T.t_complex_line, tagname="p", lineprefix=None, children=after)
                            return
                
                item.children.append(lines[startpos])
                del lines[startpos]
                
            while startpos<len(lines)-1 and getchar(lines[startpos])==prefix:
                # collect items
                item = newitem()
                item.children=[]
                appendline()
                
                while startpos<len(lines)-1 and prefix==getchar(lines[startpos]) and len(lines[startpos].lineprefix)>1:
                    appendline()

                for x in item.children:
                    x.lineprefix=x.lineprefix[1:]
                self.analyze(item.children)
                node.children.append(item)
                if prefix==';' and item.children and item.children[0].type==T.t_complex_node:
                    dd = self.splitdl(item.children[0])
                    if dd is not None:
                        break
                if prefix in ":;":
                    break
                
            lines.insert(startpos, node)
            startpos += 1
            if dd is not None:
                lines.insert(startpos, dd)
                startpos += 1
        del lines[-1] # remove guard
        
    def run(self):
        tokens = self.tokens
        i = 0
        lines = []
        startline = None
        firsttoken = None

        def getlineprefix():
            return (tokens[startline].text or "").strip()
        
        while i<len(self.tokens):
            t = tokens[i]
            if t.type in (T.t_item, T.t_colon):
                if firsttoken is None:
                    firsttoken = i
                startline = i
                i+=1
            elif t.type==T.t_newline and startline is not None:
                sub = self.tokens[startline+1:i+1]
                lines.append(T(type=T.t_complex_line, start=tokens[startline].start, len=0, children=sub, lineprefix=getlineprefix()))
                startline = None
                i+=1
            elif t.type==T.t_break:
                if startline is not None:
                    sub = self.tokens[startline+1:i]
                    lines.append(T(type=T.t_complex_line, start=tokens[startline].start, len=0, children=sub, lineprefix=getlineprefix()))
                    startline=None
                if lines:
                    self.analyze(lines)
                    self.tokens[firsttoken:i] = lines
                    i = firsttoken
                    firsttoken=None
                    lines=[]
                    continue
                    
                firsttoken = None
                
                lines = []
                i+=1
            else:
                if startline is None and lines:
                    self.analyze(lines)
                    self.tokens[firsttoken:i] = lines
                    i = firsttoken
                    lines=[]
                    firsttoken=None
                else:
                    i+=1

        if startline is not None:
            sub = self.tokens[startline+1:]
            lines.append(T(type=T.t_complex_line, start=tokens[startline].start, children=sub, lineprefix=getlineprefix()))

        if lines:
            self.analyze(lines)
            self.tokens[firsttoken:] = lines                

        
class parse_links(object):
    def __init__(self, tokens, xopts):
        self.xopts = xopts
        lang = xopts.lang
        imagemod = xopts.imagemod
        
        self.tokens = tokens
        self.lang = lang
        
        self.nshandler = xopts.nshandler
        assert self.nshandler is not None, 'nshandler not set'
        
            
        if imagemod is None:
            imagemod = util.ImageMod()
        self.imagemod = imagemod
        
        self.run()

    def handle_image_modifier(self, mod, node):
        mod_type, mod_match = self.imagemod.parse(mod)
        if mod_type is None:
            return False
        util.handle_imagemod(node, mod_type, mod_match)
        if node.thumb or node.align or node.frame=="frame":
            node.blocknode=True
            
        return True
    
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
            elif t.type == T.t_newline and len(marks) < 2:
                if stack:
                    marks = stack.pop()
                else:
                    marks = []
                i += 1
            elif t.type==T.t_special and t.text=="|":
                marks.append(i)
                i+=1
            elif t.type==T.t_2box_close and marks:
                marks.append(i)
                start = marks[0]
                
                target = T.join_as_text(tokens[start+1:marks[1]]).strip()
                target=target.strip(u"\u200e\u200f")
                if target.startswith(":"):
                    target = target[1:]
                    colon = True
                else:
                    colon = False

                ilink = self.nshandler.resolve_interwiki(target)
                if ilink:
                    url = ilink.url
                    ns = None
                    partial = ilink.partial
                    langlink = ilink.language
                    interwiki = ilink.prefix
                    full = None
                else:
                    if target.startswith('/') and self.xopts.title:
                        ns, partial, full = self.nshandler.splitname(self.xopts.title + target)
                        if full.endswith('/'):
                            full = full[:-1]
                            target = target[1:-1]
                    else:
                        ns, partial, full = self.nshandler.splitname(target)

                    if self.xopts.wikidb is not None:
                        url = self.xopts.wikidb.getURL(full)
                    else:
                        url = None
                    langlink = None
                    interwiki = None

                if not ilink and not partial:
                    i+=1
                    if stack:
                        marks=stack.pop()
                    else:
                        marks=[]
                    continue

                node = T(type=T.t_complex_link, children=[], ns=ns, colon=colon, lang=self.lang, nshandler=self.nshandler, url=url)
                if langlink:
                    node.langlink = langlink
                if interwiki:
                    node.interwiki = interwiki
                    
                sub = None
                if ns==nshandling.NS_IMAGE:
                    sub = self.extract_image_modifiers(marks, node)                        
                elif len(marks)>2:
                    sub = tokens[marks[1]+1:marks[-1]]

                if sub is None:
                    sub = [] 
                    
                node.children = sub
                tokens[start:i+1] = [node]
                node.target = target
                node.full_target = full
                if stack:
                    marks = stack.pop()
                else:
                    marks = []
                i = start+1
            else:
                i+=1




class parse_paragraphs(object):
    need_walker = False
    
    def __init__(self, tokens, xopts):
        walker = get_token_walker(skip_tags=set(["p", "ol", "ul", "table", "tr", "@section"]))
        for t in walker(tokens):
            self.tokens = t
            self.run()
        
    def run(self):
        tokens = self.tokens
        i = 0
        first = 0
        def create(delta=1):
            sub = tokens[first:i]
            if sub:
                tokens[first:i+delta] = [T(type=T.t_complex_tag, tagname='p', children=sub, blocknode=True)]

        
        while i<len(self.tokens):
            t = tokens[i]
            if t.type==T.t_break:
                create()
                first += 1
                i = first
            elif t.blocknode: # blocknode
                create(delta=0)
                first += 1
                i = first
            else:
                i+=1
                
        if first:
            create()

    

class combined_parser(object):
    def __init__(self, parsers):
        self.parsers = parsers

    def __call__(self, tokens, xopts):
        parsers = list(self.parsers)

        default_walker = get_token_walker(skip_tags=set(["table", "tr", "@section"]))
        
        while parsers:
            p = parsers.pop()

            need_walker = getattr(p, "need_walker", True)
            if need_walker:
                # print "using default token walker for", p
                walker = default_walker
                for x in walker(tokens):
                    p(x, xopts)
            else:
                p(tokens, xopts)
                

def mark_style_tags(tokens, xopts):
    tags = set("abbr tt strike ins del small sup sub b strong cite i u em big font s var kbd".split())

    todo = [(0, dict(), tokens)]

    
    def create():
        if not state or i<=start:
            return False

        children = tokens[start:i]
        for tag, tok in state.items():
            outer = T(type=T.t_complex_tag, tagname=tag, children=children, vlist=tok.vlist)
            children = [outer]
        tokens[start:i] = [outer]
        return True
            
            
    while todo:
        i, state, tokens = todo.pop()
        start = i
        while i<len(tokens):
            t = tokens[i]
            if t.type==T.t_html_tag and t.rawtagname in tags:
                del tokens[i]
                if t.tag_selfClosing:
                    continue

                if t.rawtagname in state:
                    if create():
                        start += 1
                        i = start
                    start = i
                    
                    del state[t.rawtagname]
                    continue
                    
                if create():
                    start += 1
                    i = start
                start = i
                state[t.rawtagname]=t
            elif t.type==T.t_html_tag_end and t.rawtagname in tags:
                del tokens[i]
                rawtagname = t.rawtagname
                
                if rawtagname not in state:
                    if rawtagname=="sup":
                        rawtagname="sub"
                    elif rawtagname=="sub":
                        rawtagname="sup"
                        
                if rawtagname in state:
                    if create():
                        start += 1
                        i = start
                    del state[rawtagname]
            elif t.children:
                if create():
                    start += 1
                    i = start
                assert tokens[i] is t
                if t.type in (T.t_complex_table, T.t_complex_table_row, T.t_complex_table_cell):
                    todo.append((i+1, state, tokens))
                    todo.append((0, dict(), t.children))                    
                else:    
                    todo.append((i+1, state, tokens))
                    todo.append((0, state, t.children))
                break
            else:
                i+=1
        create()
mark_style_tags.need_walker = False

class parse_uniq(object):
    def __init__(self, tokens, xopts):
        self.tagextensions=tagext.default_registry

        uniquifier = xopts.uniquifier
        if uniquifier is None:
            return

        i = 0
        while i<len(tokens):
            t = tokens[i]
            if t.type!=T.t_uniq:
                i+=1
                continue
            
            text = t.text
            try:
                match = uniquifier.uniq2repl[text]
            except KeyError:
                t.type==T.t_text
                i+=1
                continue

            vlist = match["vlist"]
            if vlist:
                vlist = util.parseParams(vlist)
            else:
                vlist = None

            inner = match["inner"]
            name = match["tagname"]
            
            try:
                m = getattr(self, "create_"+str(name))
            except AttributeError:
                m = self._create_generic
                
            tokens[i] = m(name, vlist, inner or u"", xopts)
            if tokens[i] is None:
                del tokens[i]
            else:
                i += 1
                
            
    def _create_generic(self, name, vlist, inner, xopts):
        if not vlist:
            vlist = {}
        if name in self.tagextensions:
            node = self.tagextensions[name](inner, vlist)
            if node is None:
                retval = None
            else:
                retval = T(type=T.t_complex_compat, compatnode=node)

            return retval
        
        children = [T(type=T.t_text, text=inner)]
        return T(type=T.t_complex_tag, tagname=name, vlist=vlist, children=children)

    def create_pre(self, name, vlist, inner, xopts):
        inner = util.replace_html_entities(util.remove_nowiki_tags(inner))
        return self._create_generic(name,  vlist, inner, xopts)
    
    def create_source(self, name, vlist, inner, xopts):
        children = [T(type=T.t_text, text=inner)]
        blocknode = True
        if vlist and vlist.get("enclose",  "")=="none":
            blocknode=False
            
        return T(type=T.t_complex_tag, tagname=name, vlist=vlist, children=children, blocknode=blocknode)
    
    def create_ref(self, name, vlist, inner, xopts):
        expander = xopts.expander
        if expander is not None and inner:
            inner = expander.parseAndExpand(inner, True)

        if inner:
            # <ref>* not an item</ref>
            children = parse_txt("<br />"+inner, xopts)
            if children[0].children: # paragraph had been created...
                del children[0].children[0]
            else:
                del children[0]
        else:
            children = []
            
        return T(type=T.t_complex_tag, tagname="ref", vlist=vlist, children=children)

    def create_timeline(self, name, vlist, inner, xopts):
        return T(type=T.t_complex_tag, tagname="timeline", vlist=vlist, timeline=inner, blocknode=True)

    def create_math(self, name, vlist, inner, xopts):
        return T(type=T.t_complex_tag, tagname="math", vlist=vlist, math=inner)
    
    def create_gallery(self, name, vlist, inner, xopts):
        sub = _parse_gallery_txt(inner, xopts)
        return T(type=T.t_complex_tag, tagname="gallery", vlist=vlist, children=sub, blocknode=True)

    def create_poem(self, name, vlist, inner, xopts):
        expander = xopts.expander
        if expander is not None and inner:
            inner = expander.parseAndExpand(inner, True)

        res = []
        res.append(u"\n")
        for line in inner.split("\n"):
            if line.strip():
                res.append(":")
            if line.startswith(" "):
                res.append(u"&nbsp;")
            res.append(line.strip())
            res.append(u"\n")
        res.append(u"\n")
        res = u"".join(res)
        children = parse_txt(res, xopts)
        return T(type=T.t_complex_tag, tagname="poem", vlist=vlist, children=children)
    
    def create_imagemap(self, name, vlist, inner, xopts):
        from mwlib import imgmap
        txt = inner
        t = T(type=T.t_complex_tag, tagname="imagemap", vlist=vlist)
        t.imagemap = imgmap.ImageMapFromString(txt)
        if t.imagemap.image:
            t.imagemap.imagelink = None
            s = u"[["+t.imagemap.image+u"]]"
            res = parse_txt(s, xopts)
            if res and res[0].type==T.t_complex_link and res[0].ns==6:
                t.imagemap.imagelink = res[0]

        return t

    def create_nowiki(self, name, vlist, inner, xopts):
        txt = inner
        txt = util.replace_html_entities(txt)
        return T(type=T.t_text, text=txt)

    def create_pages(self, name, vlist, inner, xopts):
        expander = xopts.expander

        if not vlist:
            vlist = {}
        s = vlist.get("from")
        e = vlist.get("to")
        children = []
        if s and e and expander:
            nshandler = expander.nshandler
            page_ns = nshandler._find_namespace("Page")[1]

            try:
                si = int(s)
                ei = int(e)
            except ValueError:
                s = nshandler.get_fqname(s, page_ns)
                e = nshandler.get_fqname(e, page_ns)
                pages = expander.db.select(s, e)
            else:
                base = vlist.get("index", "")
                base = nshandler.get_fqname(base, page_ns)
                pages = [u"%s/%s" % (base, i) for i in range(si, ei+1)]

            rawtext = u"".join(u"{{%s}}\n" % x for x in pages)
            te = expander.__class__(rawtext, pagename=xopts.pagename, wikidb=expander.db)
            children = parse_txt(te.expandTemplates(True),
                                 xopts=XBunch(**xopts.__dict__),
                                 expander=te,
                                 uniquifier=te.uniquifier)


        return T(type=T.t_complex_tag, tagname=name, vlist=vlist, children=children)


class XBunch(object):
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def __getattr__(self, name):
        return None

def fix_urllink_inside_link(tokens,  xopt):
    idx = 0
    last = None
    while idx<len(tokens)-1:
        t = tokens[idx]
        if t.type==T.t_2box_open:
            last = T.t_2box_open
        elif t.type==T.t_urllink:
            last = T.t_urllink
        elif t.type==T.t_2box_close:
            if tokens[idx+1].type==T.t_special and tokens[idx+1].text=="]" and last==T.t_urllink:
                tokens[idx], tokens[idx+1] = tokens[idx+1], tokens[idx]

        idx += 1
        

def fix_named_url_double_brackets(tokens, xopt):
    idx = 0
    while idx<len(tokens)-1:
        t = tokens[idx]
        if t.type==T.t_2box_open and tokens[idx+1].type==T.t_http_url:
            tokens[idx].text = "["
            tokens[idx].type = T.t_special
            tokens[idx+1].text = "["+tokens[idx+1].text
            tokens[idx+1].type = T.t_urllink
        idx += 1
    fix_urllink_inside_link(tokens, xopt)
    
    
def fix_break_between_pre(tokens, xopt):
    idx = 0
    while idx<len(tokens)-1:
        t = tokens[idx]
        if t.type==T.t_break and t.text.startswith(" ") and tokens[idx+1].type==T.t_pre:
            tokens[idx:idx+1] = [T(type=T.t_pre, text=" "), T(type=T.t_newline, text=u"\n")]
            idx += 2
        else:
            idx+=1

def fixlitags(tokens, xopts):
    root = T(type=T.t_complex_tag, tagname="div")
    todo = [(root, tokens)]
    while todo:
        parent, tokens = todo.pop()
        if parent.tagname not in ("ol", "ul"):
            idx = 0
            while idx<len(tokens):
                start = idx
                while idx<len(tokens) and tokens[idx].tagname=="li":
                    idx+=1

                if idx>start:
                    lst = T(type=T.t_complex_tag, tagname="ul", children=tokens[start:idx])
                    tokens[start:idx+1] = [lst]
                    idx = start+1
                else:
                    idx += 1
                    
        for t in tokens:
            if t.children:
                todo.append((t, t.children))
fixlitags.need_walker = False

def parse_txt(txt, xopts=None, **kwargs):
    if xopts is None:
        xopts = XBunch(**kwargs)
    else:
        xopts.__dict__.update(**kwargs)

    if xopts.expander is None:
        from mwlib.expander import Expander,  DictDB    
        xopts.expander = Expander("", "pagename", wikidb=DictDB())
            
    if xopts.nshandler is None:
        xopts.nshandler = nshandling.get_nshandler_for_lang(xopts.lang or 'en')
    
    xopts.imagemod = util.ImageMod(xopts.magicwords)

    uniquifier = xopts.uniquifier
    if uniquifier is None:
        uniquifier = uniq.Uniquifier()
        txt = uniquifier.replace_tags(txt)
        xopts.uniquifier = uniquifier

    tokens = tokenize(txt, uniquifier=uniquifier)
    
    td2 =  tagparser()
    a = td2.add
    
    a("code"       , 10)
    a("span"       , 20)
    
    a("li"         , 25, blocknode=True, nested=False)
    a("dl"         , 28, blocknode=True)
    a("dt"         , 26, blocknode=True, nested=False)
    a("dd"         , 26, blocknode=True, nested=True)


    td1 =  tagparser()
    a = td1.add
    a("blockquote" , 5)
    a("references" , 15)
    
    a("p"          , 30, blocknode=True, nested=False)
    a("ul"         , 35, blocknode=True)
    a("ol"         , 40, blocknode=True)
    a("center"     , 45, blocknode=True)

    td_parse_h = tagparser()
    for i in range(1, 7):
        td_parse_h.add("h%s" % i, i)
        
        
    parsers = [fixlitags,
               mark_style_tags,
               parse_singlequote,
               parse_preformatted,
               td2, 
               parse_paragraphs,
               td1, 
               parse_lines,
               parse_div,
               parse_links,
               parse_urls,
               parse_inputbox,
               td_parse_h, 
               parse_sections,
               remove_table_garbage, 
               fix_tables, 
               parse_tables,
               parse_uniq,
               fix_named_url_double_brackets, 
               fix_break_between_pre]
    
    combined_parser(parsers)(tokens, xopts)
    return tokens
