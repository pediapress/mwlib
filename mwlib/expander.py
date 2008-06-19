#! /usr/bin/env python

# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.

import sys
import re
import os
from mwlib import magics
import mwlib.log

DEBUG = "DEBUG_EXPANDER" in os.environ


log = mwlib.log.Log("expander")

splitpattern = """
({{+)                     # opening braces
|(}}+)                    # closing braces
|(\[\[|\]\])              # link
|((?:<noinclude>.*?</noinclude>)|(?:</?includeonly>))  # noinclude, comments: usually ignore
|(?P<text>(?:<nowiki>.*?</nowiki>)          # nowiki
|(?:<math>.*?</math>)
|(?:<imagemap[^<>]*>.*?</imagemap>)
|(?:<gallery[^<>]*>.*?</gallery>)
|(?:<source[^<>]*>.*?</source>)
|(?:<pre.*?>.*?</pre>)
|(?:=)
|(?:[\[\]\|{}<])                                  # all special characters
|(?:[^=\[\]\|{}<]*))                               # all others
"""

splitrx = re.compile(splitpattern, re.VERBOSE | re.DOTALL | re.IGNORECASE)

onlyincluderx = re.compile("<onlyinclude>(.*?)</onlyinclude>", re.DOTALL | re.IGNORECASE)

commentrx = re.compile(r"(\n *)?<!--.*?-->( *\n)?", re.DOTALL)

def remove_comments(txt):
    def repl(m):
        #print "M:", repr(txt[m.start():m.end()])
        if txt[m.start()]=='\n' and txt[m.end()-1]=='\n':
            return '\n'
        return (m.group(1) or "")+(m.group(2) or "")
    return commentrx.sub(repl, txt)

def preprocess(txt):
    txt=txt.replace("\t", " ")
    txt=remove_comments(txt)
    return txt

class symbols:
    bra_open = 1
    bra_close = 2
    link = 3
    noi = 4
    txt = 5

def tokenize(txt):
    txt = preprocess(txt)
                         
    if "<onlyinclude>" in txt:
        # if onlyinclude tags are used, only use text between those tags. template 'legend' is a example
        txt = "".join(onlyincluderx.findall(txt))
        
            
    tokens = []
    for (v1, v2, v3, v4, v5) in splitrx.findall(txt):
        if v5:
            tokens.append((5, v5))        
        elif v4:
            tokens.append((4, v4))
        elif v3:
            tokens.append((3, v3))
        elif v2:
            tokens.append((2, v2))
        elif v1:
            tokens.append((1, v1))

    tokens.append((None, ''))
    
    return tokens


def flatten(node, expander, variables, res):
    t=type(node)
    if t is unicode or t is str:
        res.append(node)
    elif t is list:
        for x in node:
            flatten(x, expander, variables, res)
    else:
        node.flatten(expander, variables, res)
    

class Node(object):
    def __init__(self):
        self.children = []

    def __repr__(self):
        return "<%s %s children>" % (self.__class__.__name__, len(self.children))

    def __iter__(self):
        for x in self.children:
            yield x

    def show(self, out=None):
        show(self, out=out)

        
    def flatten(self, expander, variables, res):
        for x in self.children:
            if isinstance(x, basestring):
                res.append(x)
            else:
                flatten(x, expander, variables, res)
        
class Variable(Node):
    def flatten(self, expander, variables, res):
        name = []
        flatten(self.children[0], expander, variables, name)
        name = u"".join(name).strip()
        if len(name)>256*1024:
            raise MemoryLimitError("template name too long: %s bytes" % (len(name),))

        v = variables.get(name, None)

        if v is None:
            if len(self.children)>1:
                flatten(self.children[1:], expander, variables, res)
            else:
                pass
                # FIXME. breaks If
                #res.append(u"{{{%s}}}" % (name,))
        else:
            res.append(v)

class Template(Node):
    def flatten(self, expander, variables, res):
        name = []
        flatten(self.children[0], expander, variables, name)
        name = u"".join(name).strip()
        if len(name)>256*1024:
            raise MemoryLimitError("template name too long: %s bytes" % (len(name),))

        remainder = None
        if ":" in name:
            try_name, try_remainder = name.split(':', 1)
            if expander.resolver.has_magic(try_name):
                name=try_name
                remainder = try_remainder
        if name=='#if':
            #print "SPECIALCASE", (name, remainder)
            res.append(maybe_newline)
            tmp = []
            if remainder:
                if len(self.children)>=2:
                    flatten(self.children[1], expander, variables, tmp)
            else:
                if len(self.children)>=3:
                    flatten(self.children[2], expander, variables, tmp)
            res.append(u"".join(tmp).strip())
            res.append(dummy_mark)
            return

        #print "NAME:", (name, remainder)
        
        var = ArgumentList()

        if remainder is not None:
            tmpnode=Node()
            tmpnode.children.append(remainder)
            var.append(LazyArgument(tmpnode, expander, variables))
        
        for x in self.children[1:]:
            var.append(LazyArgument(x, expander, variables))

        rep = expander.resolver(name, var)

        if rep is not None:
            res.append(maybe_newline)
            res.append(rep)
            res.append(dummy_mark)
        else:            
            p = expander.getParsedTemplate(name)
            if p:
                if DEBUG:
                    msg = "EXPANDING %r %r  ===> " % (name, var)
                    oldidx = len(res)
                res.append(mark_start(repr(name)))
                res.append(maybe_newline)
                flatten(p, expander, var, res)
                res.append(mark_end(repr(name)))

                if DEBUG:
                    msg += repr("".join(res[oldidx:]))
                    print msg

def show(node, indent=0, out=None):
    if out is None:
        out=sys.stdout

    out.write("%s%r\n" % ("  "*indent, node))
    if isinstance(node, basestring):
        return
    for x in node.children:
        show(x, indent+1, out)

def optimize(node):
    if isinstance(node, basestring):
        return node

    if type(node) is Node and len(node.children)==1:
        return optimize(node.children[0])

    for i, x in enumerate(node.children):
        node.children[i] = optimize(x)
    return node

    
class Parser(object):
    template_ns = set([ ((5, u'Template'), (5, u':')),
                        ((5, u'Vorlage'), (5, u':')),
                        ])


    def __init__(self, txt):
        if isinstance(txt, str):
            txt = unicode(txt)
            
        self.txt = txt
        self.tokens = tokenize(txt)
        self.pos = 0

    def getToken(self):
        return self.tokens[self.pos]

    def setToken(self, tok):
        self.tokens[self.pos] = tok


    def variableFromChildren(self, children):
        v=Variable()
        name = Node()
        v.children.append(name)

        try:
            idx = children.index(u"|")
        except ValueError:
            name.children = children
        else:
            name.children = children[:idx]            
            v.children.extend(children[idx+1:])
        return v
        
    def _eatBrace(self, num):
        ty, txt = self.getToken()
        assert ty == symbols.bra_close
        assert len(txt)>= num
        newlen = len(txt)-num
        if newlen==0:
            self.pos+=1
            return
        
        if newlen==1:
            ty = symbols.txt

        txt = txt[:newlen]
        self.setToken((ty, txt))
        

    def templateFromChildren(self, children):
        t=Template()
        # find the name
        name = Node()
        t.children.append(name)
        idx = 0
        for idx, c in enumerate(children):
            if c==u'|':
                break
            name.children.append(c)


        # find the arguments
        

        arg = Node()

        linkcount = 0
        for c in children[idx+1:]:
            if c==u'[[':
                linkcount += 1
            elif c==']]':
                linkcount -= 1
            elif c==u'|' and linkcount==0:
                t.children.append(arg)
                arg = Node()
                continue
            arg.children.append(c)


        if arg.children:
            t.children.append(arg)


        return t
        
    def parseOpenBrace(self):
        ty, txt = self.getToken()
        n = Node()

        numbraces = len(txt)
        self.pos += 1
        
        while 1:
            ty, txt = self.getToken()
            if ty==symbols.bra_open:
                n.children.append(self.parseOpenBrace())
            elif ty is None:
                break
            elif ty==symbols.bra_close:
                closelen = len(txt)
                if closelen==2 or numbraces==2:
                    t=self.templateFromChildren(n.children)
                    n=Node()
                    n.children.append(t)
                    self._eatBrace(2)
                    numbraces-=2
                else:
                    v=self.variableFromChildren(n.children)
                    n=Node()
                    n.children.append(v)
                    self._eatBrace(3)
                    numbraces -= 3

                if numbraces==0:
                    break
                elif numbraces==1:
                    n.children.insert(0, "{")
                    break
            elif ty==symbols.noi:
                self.pos += 1 # ignore <noinclude>
            else: # link, txt
                n.children.append(txt)
                self.pos += 1                

        return n
        
    def parse(self):
        n = Node()
        while 1:
            ty, txt = self.getToken()
            if ty==symbols.bra_open:
                n.children.append(self.parseOpenBrace())
            elif ty is None:
                break
            elif ty==symbols.noi:
                self.pos += 1   # ignore <noinclude>
            else: # bra_close, link, txt                
                n.children.append(txt)
                self.pos += 1
        return n

def parse(txt):
    return optimize(Parser(txt).parse())

class MemoryLimitError(Exception):
    pass

class LazyArgument(object):
    def __init__(self, node, expander, variables):
        self.node = node
        self.expander = expander
        self._flatten = None
        self.variables = variables
        self._splitflatten = None

    def _flattennode(self, n):
        arg=[]
        flatten(n, self.expander, self.variables, arg)
        _insert_implicit_newlines(arg)
        arg = u"".join(arg)

        if len(arg)>256*1024:
            raise MemoryLimitError("template argument too long: %s bytes" % (len(arg),))
        return arg

    def splitflatten(self):
        if self._splitflatten is None:
            try:
                idx = self.node.children.index(u'=')
            except (ValueError, AttributeError):
                name = None
                val = self.node
            else:
                name = self.node
                val = Node()
                val.children[:] = self.node.children[idx+1:]
                oldchildren = self.node.children[:]
                del self.node.children[idx:]

                name = self._flattennode(name)
                self.node.children = oldchildren
                
            val = self._flattennode(val)

            self._splitflatten = name, val
        return self._splitflatten
    
            
    def flatten(self):
        if self._flatten is None:            
            self._flatten = self._flattennode(self.node).strip()
            
            arg=[]
            flatten(self.node, self.expander, self.variables, arg)
            _insert_implicit_newlines(arg)
            arg = u"".join(arg).strip()
            if len(arg)>256*1024:
                raise MemoryLimitError("template argument too long: %s bytes" % (len(arg),))
            
            self._flatten = arg
        return self._flatten

class ArgumentList(object):
    def __init__(self):
        self.args = []
        self.namedargs = {}
    def __repr__(self):
        return "<ARGLIST args=%r>" % ([x.flatten() for x in self.args],)
    def append(self, a):
        self.args.append(a)

    def __iter__(self):
        for x in self.args:
            yield x

    def __getslice__(self, i, j):
        for x in self.args[i:j]:
            yield x.flatten()
        
    def __len__(self):
        return len(self.args)

    def __getitem__(self, n):
        return self.get(n, None) or u''
        
    def get(self, n, default):
        if isinstance(n, (int, long)):
            try:
                a=self.args[n]
            except IndexError:
                return default
            return a.flatten()

        assert isinstance(n, basestring), "expected int or string"

        varcount=1
        if n not in self.namedargs:
            for x in self.args:
                name, val = x.splitflatten()
                
                
                if name is not None:
                    name = name.strip()
                    val = val.strip()
                    self.namedargs[name] = val
                    if n==name:
                        return val
                else:
                    name = str(varcount)
                    varcount+=1
                    self.namedargs[name] = val 

                    if n==name:
                        return val
            self.namedargs[n] = None

        val = self.namedargs[n]
        if val is None:
            return default
        return val
    
def is_implicit_newline(raw):
    """should we add a newline to templates starting with *, #, :, ;, {|
    see: http://meta.wikimedia.org/wiki/Help:Newlines_and_spaces#Automatic_newline_at_the_start
    """
    sw = raw.startswith
    for x in ('*', '#', ':', ';', '{|'):
        if sw(x):
            return True
    return False 

class mark(unicode):
    def __new__(klass, msg):
        r=unicode.__new__(klass)
        r.msg = msg
        return r
    
    def __repr__(self):
        return '<%s %r>' % (self.__class__.__name__, self.msg,)

class mark_start(mark): pass
class mark_end(mark): pass
class mark_maybe_newline(mark): pass

maybe_newline = mark_maybe_newline('maybe_newline')
dummy_mark = mark('dummy')

def _insert_implicit_newlines(res, maybe_newline=maybe_newline):
    # do not pass the second argument
    res.append(dummy_mark)
    res.append(dummy_mark)
    for i, p in enumerate(res):
        if p is maybe_newline:
            s1 = res[i+1]
            s2 = res[i+2]
            if isinstance(s1, mark):
                continue
            if len(s1)>=2:
                if is_implicit_newline(s1):
                    res[i] = '\n'
            else:
                if is_implicit_newline(''.join([s1, s2])):
                    res[i] = '\n'
    del res[-2:]
    
class Expander(object):
    def __init__(self, txt, pagename="", wikidb=None):
        assert wikidb is not None, "must supply wikidb argument in Expander.__init__"
        self.db = wikidb
        self.resolver = magics.MagicResolver(pagename=pagename)
        self.resolver.wikidb = wikidb

        self.parsed = parse(txt)
        #show(self.parsed)
        self.parsedTemplateCache = {}
        
    def getParsedTemplate(self, name):
        if name.startswith("[["):
            return None

        try:
            return self.parsedTemplateCache[name]
        except KeyError:
            pass

        if name.startswith(":"):
            log.info("including article")
            raw = self.db.getRawArticle(name[1:])
        else:
            raw = self.db.getTemplate(name, True)
            
        if raw is None:
            log.warn("no template", repr(name))
            res = None
        else:
            log.info("parsing template", repr(name))
            res = parse(raw)
            if DEBUG:
                print "TEMPLATE:", name, repr(raw)
                res.show()
                
        self.parsedTemplateCache[name] = res
        return res
            
        
    def expandTemplates(self):
        res = []
        flatten(self.parsed, self, ArgumentList(), res)
        _insert_implicit_newlines(res)
        return u"".join(res)


class DictDB(object):
    """wikidb implementation used for testing"""
    def __init__(self, *args, **kw):
        if args:
            self.d, = args
        else:
            self.d = {}
        
        self.d.update(kw)

        normd = {}
        for k, v in self.d.items():
            normd[k.lower()] = v
        self.d = normd
        
    def getRawArticle(self, title):
        return self.d[title.lower()]

    def getTemplate(self, title, dummy):
        return self.d.get(title.lower(), u"")
    
def expandstr(s, expected=None, wikidb=None, pagename='thispage'):
    """debug function. expand templates in string s"""
    if wikidb:
        db = wikidb
    else:
        db = DictDB(dict(a=s))

    te = Expander(s, pagename=pagename, wikidb=db)
    res = te.expandTemplates()
    print "EXPAND: %r -> %r" % (s, res)
    if expected is not None:
        assert res==expected, "expected %r, got %r" % (expected, res)
    return res

if __name__=="__main__":
    #print splitrx.groupindex
    d=unicode(open(sys.argv[1]).read(), 'utf8')
    e = Expander(d)
    print e.expandTemplates()
