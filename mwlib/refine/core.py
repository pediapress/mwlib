#! /usr/bin/env python

# Copyright (c) 2007-2009 PediaPress GmbH
# See README.txt for additional licensing information.

from mwlib.utoken import tokenize, show, token as T, walknode, walknodel
from mwlib.refine import util
from mwlib import namespace, tagext, uniq

from mwlib.refine.parse_table import parse_tables, parse_table_cells, parse_table_rows

# try:
#     from blist import blist
#     import pkg_resources
#     pkg_resources.require("blist>=0.9.15")
# except ImportError:
#     # import warnings
#     # warnings.warn("using normal list. parsing might be slower. please run 'easy_install blist'")
#     blist = list

blist = list

    
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

def get_token_walker(skip_types=set(), skip_tags=set()):
    def walk(tokens):
        todo = [tokens]
        yield tokens
        
        while todo:
            tmp = todo.pop()
            for x in tmp:
                if x.type not in skip_types and x.tagname not in skip_tags:
                    if x.children is not None:
                        yield x.children
                        todo.append(x.children)
                else:
                    # print "skip", x, x.children
                    if x.children is not None:
                        todo.append(x.children)
    return walk

def get_recursive_tag_parser(tagname, break_at=None, blocknode=False):
    if break_at is None:
        break_at = lambda _: False
        
    def recursive_parse_tag(tokens, xopts):            
        i = 0
        stack = []

        def create():
            sub = tokens[start+1:i]
            return [T(type=T.t_complex_tag, children=sub, tagname=tagname, blocknode=blocknode, vlist=tokens[start].vlist)]
        
        while i<len(tokens):
            t = tokens[i]
            if stack and break_at(t):
                start = stack.pop()
                tokens[start:i] = create()
                i=start+1
            elif t.type==T.t_html_tag and t.tagname==tagname:
                if t.tag_selfClosing:
                    tokens[i].type = T.t_complex_tag
                else:
                    stack.append(i)
                i+=1
            elif t.type==T.t_html_tag_end and t.tagname==tagname:
                if stack:
                    start = stack.pop()
                    tokens[start:i+1] = create()
                    i = start+1
                else:
                    i+=1
            else:
                i+= 1

        while stack:
            start = stack.pop()
            tokens[start:] = create()

    recursive_parse_tag.__name__ += "_"+tagname
    
    return recursive_parse_tag
    
parse_div = get_recursive_tag_parser("div", blocknode=True)
parse_center = get_recursive_tag_parser("center", blocknode=True)

def _li_break_at(token):
    if token.type==T.t_html_tag and token.tagname=="li":
        return True
    return False
parse_li = get_recursive_tag_parser("li", _li_break_at, blocknode=True)
parse_ol = get_recursive_tag_parser("ol", blocknode=True)
parse_ul = get_recursive_tag_parser("ul", blocknode=True)
parse_span = get_recursive_tag_parser("span")
parse_p = get_recursive_tag_parser("p", blocknode=True)
parse_references = get_recursive_tag_parser("references")

parse_blockquote = get_recursive_tag_parser("blockquote")
parse_code_tag = get_recursive_tag_parser("code")

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

        linode = parse_txt(u'[['+x+']]', xopts)

        if linode:
            n = linode[0]
            if n.ns==namespace.NS_IMAGE:
                sub.append(n)
                continue
        sub.append(T(type=T.t_text, text=x))
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
            l1 = tokens[current.start].text.count("=")
            l2 = tokens[current.endtitle].text.count("=")
            level = min (l1, l2)

            # FIXME: make this a caption
            caption = T(type=T.t_complex_node, start=0, len=0, children=tokens[current.start+1:current.endtitle]) 
            if l2>l1:
                caption.children.append(T(type=T.t_text, text=u"="*(l2-l1)))
            elif l1>l2:
                caption.children.insert(0, T(type=T.t_text, text=u"="*(l1-l2)))

            body = T(type=T.t_complex_node, children=tokens[current.endtitle+1:i])
              
            sect = T(type=T.t_complex_section, start=0, children=blist([caption, body]), level=level, blocknode=True)
            tokens[current.start:i] = [sect] 
            

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
                    styles[i].children = blist([inner])
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
    def __init__(self, tokens, xopts):
        self.tokens = tokens
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
                lines[startpos].type = T.t_complex_node
                startpos+=1
                continue
                
            if prefix==':':
                node = T(type=T.t_complex_style, caption=':')
                newitem = lambda: T(type=T.t_complex_node, blocknode=True)
            elif prefix=='*':
                node = T(type=T.t_complex_tag, tagname="ul")
                newitem = lambda: T(type=T.t_complex_tag, tagname="li", blocknode=True)
            elif prefix=="#":
                node = T(type=T.t_complex_tag, tagname="ol")
                newitem = lambda: T(type=T.t_complex_tag, tagname="li", blocknode=True)
            elif prefix==';':
                node = T(type=T.t_complex_style, caption=';')
                newitem = lambda: T(type=T.t_complex_node, blocknode=True)
            else:
                assert 0
                
            node.children = blist()
            dd = None
            while startpos<len(lines)-1 and getchar(lines[startpos])==prefix:
                # collect items
                item = newitem()
                item.children=blist()
                item.children.append(lines[startpos])
                del lines[startpos]
                
                while startpos<len(lines)-1 and prefix==getchar(lines[startpos]) and len(lines[startpos].lineprefix)>1:
                    item.children.append(lines[startpos])
                    del lines[startpos]

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
                                   
        while i<len(self.tokens):
            t = tokens[i]
            if t.type in (T.t_item, T.t_colon):
                if firsttoken is None:
                    firsttoken = i
                startline = i
                i+=1
            elif t.type==T.t_newline and startline is not None:
                sub = self.tokens[startline+1:i+1]
                lines.append(T(type=T.t_complex_line, start=tokens[startline].start, len=0, children=sub, lineprefix=tokens[startline].text))
                startline = None
                i+=1
            elif t.type==T.t_break:
                if startline is not None:
                    sub = self.tokens[startline+1:i]
                    lines.append(T(type=T.t_complex_line, start=tokens[startline].start, len=0, children=sub, lineprefix=tokens[startline].text))
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
                    starttoken=None
                    lines=[]
                    firsttoken=None
                else:
                    i+=1

        if startline is not None:
            sub = self.tokens[startline+1:]
            lines.append(T(type=T.t_complex_line, start=tokens[startline].start, len=0, children=sub, lineprefix=tokens[startline].text))

        if lines:
            self.analyze(lines)
            self.tokens[firsttoken:] = lines                

        
class parse_links(object):
    def __init__(self, tokens, xopts):
        lang = xopts.lang
        interwikimap = xopts.interwikimap
        imagemod = xopts.imagemod
        
        self.tokens = tokens
        self.lang = lang
        self.interwikimap = interwikimap
        
        nsmap = namespace.namespace_maps.get(lang)
        if nsmap is None and lang:
            nsmap = namespace.namespace_maps.get(lang+"+en_mw")

        self.nsmap = nsmap
            
        if imagemod is None:
            imagemod = util.ImageMod()
        self.imagemod = imagemod
        
        self.run()

    def handle_image_modifier(self, mod, node):
        mod_type, mod_match = self.imagemod.parse(mod)
        if mod_type is None:
            return False
        util.handle_imagemod(node, mod_type, mod_match)
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
            elif t.type==T.t_special and t.text=="|":
                marks.append(i)
                i+=1
            elif t.type==T.t_2box_close and marks:
                marks.append(i)
                start = marks[0]
                
                target = T.join_as_text(tokens[start+1:marks[1]]).strip()
                if target.startswith(":"):
                    target = target[1:]
                    colon = True
                else:
                    colon = False



                ns, partial, full = namespace.splitname(target, nsmap=self.nsmap)
 
                if not partial:
                    i+=1
                    if stack:
                        marks=stack.pop()
                    else:
                        marks=[]                        
                    continue
                else:
                    langlink = None
                    interwiki = None
                    
                    if ns==namespace.NS_MAIN:
                        # could be an interwiki/language link. -> set ns=None
                        
                        if self.interwikimap and ':' in target:
                            prefix = target.split(":")[0]
                            r = self.interwikimap.get(prefix.strip().lower(), None)
                            if r is not None:
                                ns = None
                                if 'language' in r:
                                    langlink = r['language']
                                else:
                                    interwiki = r.get('renamed', prefix)
                                    
                            if prefix.strip().lower()=="arz":
                                langlink = "arz"
                                interwiki = None
                                ns = None
                                
                    node = T(type=T.t_complex_link, start=0, len=0, children=blist(), ns=ns, colon=colon, lang=self.lang, nsmap=self.nsmap)
                    if langlink:
                        node.langlink = langlink
                    if interwiki:
                        node.interwiki = interwiki
                        
                    sub = None
                    if ns==namespace.NS_IMAGE:
                        sub = self.extract_image_modifiers(marks, node)                        
                    elif len(marks)>2:
                        sub = tokens[marks[1]+1:marks[-1]]

                    if sub is None:
                        sub = [] #T(type=T.t_text, start=0, len=0, text=target)]
                        
                    node.children = sub
                    tokens[start:i+1] = [node]
                    node.target = target
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
        walker = get_token_walker(skip_tags=set(["p", "ol", "ul", "table"]), skip_types=set([T.t_complex_section]))
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

        default_walker = get_token_walker(skip_tags=set(["table", "tr"]), skip_types=set([T.t_complex_section]))
        
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
    tags = set("tt strike ins del small sup sub b strong cite i u em big font".split())

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
            if t.type==T.t_html_tag and t.tagname in tags:
                del tokens[i]
                if t.tag_selfClosing:
                    continue
                if create():
                    start += 1
                    i = start
                start = i
                state[t.tagname]=t
            elif t.type==T.t_html_tag_end and t.tagname in tags:
                del tokens[i]
                if t.tagname in state:
                    create()
                    start += 1
                    i = start
                    del state[t.tagname]
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


parse_h_tags = combined_parser(
    [get_recursive_tag_parser("h%s" % x) for x in range(6,0,-1)])

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

                 
    def create_source(self, name, vlist, inner, xopts):
        children = [T(type=T.t_text, text=inner)]
        return T(type=T.t_complex_tag, tagname=name, vlist=vlist, children=children, blocknode=True)
    
    def create_ref(self, name, vlist, inner, xopts):
        expander = xopts.expander
        if expander is not None and inner:
            inner = expander.parseAndExpand(inner, True)

        if inner:
            # <ref>* not an item</ref>
            children = parse_txt("<br />"+inner, xopts)
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

class XBunch(object):
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def __getattr__(self, name):
        return None

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
        
    interwikimap = xopts.interwikimap
    
    if interwikimap is None:
        from mwlib.lang import languages
        interwikimap = {}
        for prefix, renamed in namespace.dummy_interwikimap.items():
            interwikimap[prefix] = {'renamed': renamed}
        for lang in languages:
            interwikimap[lang] = {'language': True}
    xopts.interwikimap = interwikimap
    
    xopts.imagemod = util.ImageMod(xopts.magicwords)

    uniquifier = xopts.uniquifier
    if uniquifier is None:
        uniquifier = uniq.Uniquifier()
        txt = uniquifier.replace_tags(txt)
        xopts.uniquifier = uniquifier
    tokens = blist(tokenize(txt, uniquifier=uniquifier))
    
    parsers = [fixlitags,
               mark_style_tags,
               parse_singlequote,
               parse_urls,
               parse_preformatted,
               parse_paragraphs,
               parse_lines,
               parse_blockquote, parse_code_tag, 
               parse_references, parse_span, parse_li, parse_p, parse_ul, parse_ol,
               parse_center,
               parse_links,
               parse_inputbox,
               parse_h_tags,
               parse_sections,
               parse_div, parse_tables, parse_uniq]

    combined_parser(parsers)(tokens, xopts)
    return tokens
