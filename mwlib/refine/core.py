#! /usr/bin/env python

# Copyright (c) 2007-2009 PediaPress GmbH
# See README.txt for additional licensing information.

import sys
from mwlib.utoken import tokenize, show, token as T, walknode
from mwlib.refine import util
from mwlib import namespace, tagext, uniq

from mwlib.refine.parse_table import parse_tables, parse_table_cells, parse_table_rows

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
T.t_complex_indent = "indent"
T.t_complex_line = "line"
T.t_complex_named_url = "named_url"
T.t_complex_style = "style"
T.t_complex_node = "node"
T.t_complex_preformatted = "preformatted"
T.t_complex_compat = "compat"

T.t_vlist = "vlist"

T.children = None


def get_recursive_tag_parser(tagname, break_at=None, blocknode=False):
    if break_at is None:
        break_at = lambda _: False
        
    def recursive_parse_tag(tokens, refined, **kwargs):            
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
                refined.append(tokens[start])
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
                    refined.append(tokens[start])
                    i = start+1
                else:
                    i+=1
            else:
                i+= 1

        while stack:
            start = stack.pop()
            tokens[start:] = create()
            refined.append(tokens[start])

        refined.append(tokens)
    recursive_parse_tag.__name__ += "_"+tagname
    
    return recursive_parse_tag
    
parse_div = get_recursive_tag_parser("div", blocknode=True)
parse_center = get_recursive_tag_parser("center", blocknode=True)

def _li_break_at(token):
    if token.type==T.t_html_tag and token.tagname=="li":
        return True
    return False
parse_li = get_recursive_tag_parser("li", _li_break_at)
parse_ol = get_recursive_tag_parser("ol", blocknode=True)
parse_ul = get_recursive_tag_parser("ul", blocknode=True)
parse_span = get_recursive_tag_parser("span")
parse_p = get_recursive_tag_parser("p", blocknode=True)
parse_references = get_recursive_tag_parser("references")

parse_blockquote = get_recursive_tag_parser("blockquote")
parse_code_tag = get_recursive_tag_parser("code")

def parse_inputbox(tokens, refined, **kwargs):
    get_recursive_tag_parser("inputbox")(tokens, [], **kwargs)
    
    for t in tokens:
        if t.tagname=='inputbox':
            t.inputbox = T.join_as_text(t.children)
            del t.children[:]
    refined.append(tokens)

def _parse_gallery_txt(txt, **kwargs):
    lines = [x.strip() for x in txt.split("\n")]
    sub = []
    for x in lines:
        if not x:
            continue

        linode = parse_txt(u'[['+x+']]', **kwargs)

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
    def __init__(self, tokens, refined, **kwargs):
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

            # FIXME: make this a caption
            caption = T(type=T.t_complex_node, start=0, len=0, children=tokens[current.start+1:current.endtitle]) 
            if l2>l1:
                caption.children.append(T(type=T.t_text, text=u"="*(l2-l1)))
            elif l1>l2:
                caption.children.insert(0, T(type=T.t_text, text=u"="*(l1-l2)))

            body = T(type=T.t_complex_node, children=tokens[current.endtitle+1:i])
              
            sect = T(type=T.t_complex_section, start=0, children=blist([caption, body]), level=level, blocknode=True)
            tokens[current.start:i] = [sect] 
            
            self.refined.append(caption)
            self.refined.append(body)

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

class parse_urls(object):
    def __init__(self, tokens, refined, **kwargs):
        self.tokens = tokens
        self.refined = refined
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
                self.refined.append(sub)
                i = start
                start = None
            else:
                i+=1
                
        self.refined.append(tokens)

class parse_singlequote(object):
    def __init__(self, tokens, refined, **kwargs):
        self.tokens = tokens
        self.refined = refined
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
    def __init__(self, tokens, refined, **kwargs):
        self.tokens = tokens
        self.refined = refined
        self.run()

    def run(self):
        #spec = object()
        
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
                tokens[start:i+1] = [T(type=T.t_complex_preformatted, children=tokens[start+1:i+1], blocknode=True)]
                self.refined.append(tokens[start].children)
                i = start+1
                start = None
            elif t.blocknode or (t.type==T.t_complex_tag and t.tagname in ("blockquote", "table", "timeline", "div")):
                start = None
                i+=1
            else:
                i+=1

        if start is not None:
            tokens[start:i+1] = [T(type=T.t_complex_preformatted, children=tokens[start+1:i+1], blocknode=True)]
            self.refined.append(tokens[start].children)
        self.refined.append(tokens)
       
                
            
class parse_lines(object):
    def __init__(self, tokens, refined, **kwargs):
        self.tokens = tokens
        self.refined = refined
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
                self.refined.append(lines[startpos].children)
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
                    
            lines.insert(startpos, node)
            startpos += 1
            if dd is not None:
                lines.insert(startpos, dd)
                self.refined.append(dd.children)
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

        self.refined.append(tokens)
        
class parse_links(object):
    def __init__(self, tokens, refined, lang=None, interwikimap=None, imagemod=None, **kwargs):
        self.tokens = tokens
        self.refined = refined
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
                    self.refined.append(sub)
                    if stack:
                        marks = stack.pop()
                    else:
                        marks = []
                    i = start+1
            else:
                i+=1

        self.refined.append(tokens)



class parse_paragraphs(object):
    def __init__(self, tokens, refined, **kwargs):
        self.tokens = tokens
        self.refined = refined
        self.run()

    def run(self):
        tokens = self.tokens
        i = 0
        first = 0
        def create(delta=1):
            sub = tokens[first:i]
            if sub:
                tokens[first:i+delta] = [T(type=T.t_complex_tag, tagname='p', children=sub, blocknode=True)]
                self.refined.append(tokens[first])

        
        lastpre = None
        while i<len(self.tokens):
            t = tokens[i]
            if t.type==T.t_break:
                create()
                first += 1
                i = first
                lastpre = None
            elif t.blocknode: # blocknode
                if lastpre:
                    lastpre.type=T.t_text
                create(delta=0)
                first += 1
                i = first
                lastpre = None
            else:
                if t.type==T.t_newline:
                    lastpre = None
                elif t.type==T.t_pre:
                    lastpre = t
                i+=1
                
        if first:
            create()
            
        self.refined.append(tokens)

class parse_tagextensions(object):
    def __init__(self, tokens, refined, **kwargs):
        self.tokens = tokens
        self.refined = refined
        self.tagextensions=tagext.default_registry
        self.run()
        
    def run(self):
        tokens = self.tokens
        i = 0
        start = None

        def create():
            txt = u''.join([x.text for x in tokens[start+1:i]])
            
            node = self.tagextensions[tagname](txt, tokens[start].vlist)
            if node is None:
                repl = []
            else:
                repl = [T(type=T.t_complex_compat, compatnode=node)]
            tokens[start:i+1] = repl
        
        while i<len(tokens):
            t = tokens[i]
            if start is None and t.type==T.t_html_tag and t.tagname in self.tagextensions:
                start = i
                tagname = t.tagname
            elif start is not None and t.type==T.t_html_tag_end and t.tagname==tagname:
                create()
                i = start+1
                start = None
            else:
                i+=1
        if start:
            create()
        self.refined.append(tokens)
        
class combined_parser(object):
    def __init__(self, parsers):
        self.parsers = parsers

    def __call__(self, tokens, refined, **kwargs):
        parsers = list(self.parsers)
        refine = [tokens]
        
        while parsers:
            p = parsers.pop()
            #print "doing", p, "on:", refine
            
            if not parsers:
                next = refined
            else:
                next = []

            for x in refine:
                if isinstance(x, (list, blist, tuple)):
                    toks = x
                else:
                    toks = x.children
                p(toks, next, **kwargs)

            refine = next

def mark_style_tags(tokens):
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
                    i = start+1
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

parse_h_tags = combined_parser(
    [get_recursive_tag_parser("h%s" % x) for x in range(6,0,-1)])

class parse_uniq(object):
    def __init__(self, tokens, refined, **kw):
        refined.append(tokens)
        uniquifier = kw.get("uniquifier")
        if uniquifier is None:
            return
        
        for i, t in enumerate(tokens):
            if t.type!=T.t_uniq:
                continue
            
            text = t.text
            try:
                name, orig, groupdict = uniquifier.uniq2repl[text]
            except KeyError:
                t.type==T.t_text
                continue
            
            vlist = groupdict.get(name+"_vlist")
            if vlist:
                vlist = util.parseParams(vlist)
            else:
                vlist = None

            if name=="nowiki":
                inner = groupdict.get("nowiki")
            else:
                inner = groupdict.get(name+"_inner", u"")

            try:
                m = getattr(self, "create_"+str(name))
            except AttributeError:
                m = self._create_generic
                
            tokens[i] = m(name, vlist, inner, **kw)
                
    def _create_generic(self, name, vlist, inner, **kw):
        children = [T(type=T.t_text, text=inner)]
        return T(type=T.t_complex_tag, tagname=name, vlist=vlist, children=children)

    def create_source(self, name, vlist, inner, **kw):
        children = [T(type=T.t_text, text=inner)]
        return T(type=T.t_complex_tag, tagname=name, vlist=vlist, children=children, blocknode=True)
    
    def create_ref(self, name, vlist, inner, **kw):
        expander = kw.get("expander")
        if expander is not None and inner:
            inner = expander.parseAndExpand(inner, True)
        children = parse_txt(inner or u"", **kw)
        
        return T(type=T.t_complex_tag, tagname="ref", vlist=vlist, children=children)

    def create_timeline(self, name, vlist, inner, **kw):
        return T(type=T.t_complex_tag, tagname="timeline", vlist=vlist, timeline=inner, blocknode=True)

    def create_math(self, name, vlist, inner, **kw):
        return T(type=T.t_complex_tag, tagname="math", vlist=vlist, math=inner)
    
    def create_gallery(self, name, vlist, inner, **kw):
        sub = _parse_gallery_txt(inner, **kw)
        return T(type=T.t_complex_tag, tagname="gallery", vlist=vlist, children=sub, blocknode=True)

    def create_imagemap(self, name, vlist, inner, **kw):
        from mwlib import imgmap
        txt = inner
        t = T(type=T.t_complex_tag, tagname="imagemap", vlist=vlist)
        t.imagemap =imgmap.ImageMapFromString(txt)
        if t.imagemap.image:
            s = u"[["+t.imagemap.image+u"]]"
            res = parse_txt(s, **kw)
            if res and res[0].type==T.t_complex_link and res[0].ns==6:
                t.imagemap.imagelink = res[0]

            show(res)
        return t

    def create_nowiki(self, name, vlist, inner, **kw):
        txt = inner
        txt = util.replace_html_entities(txt)
        return T(type=T.t_text, text=txt)
                        
def parse_txt(txt, interwikimap=None, **kwargs):
    if interwikimap is None:
        from mwlib.lang import languages
        interwikimap = {}
        for prefix, renamed in namespace.dummy_interwikimap.items():
            interwikimap[prefix] = {'renamed': renamed}
        for lang in languages:
            interwikimap[lang] = {'language': True}
    
    kwargs['imagemod'] = util.ImageMod(kwargs.get('magicwords'))

    uniquifier = kwargs.get("uniquifier")
    if uniquifier is None:
        uniquifier = uniq.Uniquifier()
        txt = uniquifier.replace_tags(txt)
        kwargs["uniquifier"] = uniquifier
    tokens = blist(tokenize(txt, uniquifier=uniquifier))
    
    refine = [tokens]
    parsers = [parse_singlequote, parse_urls,
               parse_preformatted,
               parse_paragraphs,
               parse_lines,
               parse_blockquote, parse_code_tag, 
               parse_references, parse_span, parse_li, parse_p, parse_ul, parse_ol, parse_links,
               parse_inputbox,
               parse_h_tags,
               parse_sections,
               parse_center, parse_div, parse_tables, parse_tagextensions, parse_uniq]


    refined = []
    combined_parser(parsers)(tokens, refined, interwikimap=interwikimap, **kwargs)
    mark_style_tags(tokens)
    return tokens

