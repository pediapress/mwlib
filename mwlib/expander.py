#! /usr/bin/env python

# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.

import sys
import re

from mwlib import magics
import mwlib.log

log = mwlib.log.Log("expander")

splitpattern = """
({{+)                     # opening braces
|(}}+)                    # closing braces
|(\[\[|\]\])              # link
|((?:<noinclude>.*?</noinclude>)|(?:</?includeonly>))  # noinclude, comments: usually ignore
|(?P<text>(?:<nowiki>.*?</nowiki>)          # nowiki
|(?:<!--.*?-->)
|(?:<math>.*?</math>)
|(?:<imagemap[^<>]*>.*?</imagemap>)
|(?:<gallery[^<>]*>.*?</gallery>)
|(?:<pre.*?>.*?</pre>)
|(?:[:\[\]\|{}<])                                  # all special characters
|(?:[^\[\]\|:{}<]*))                               # all others
"""

splitrx = re.compile(splitpattern, re.VERBOSE | re.DOTALL | re.IGNORECASE)

onlyincluderx = re.compile("<onlyinclude>(.*?)</onlyinclude>", re.DOTALL | re.IGNORECASE)


class symbols:
    bra_open = 1
    bra_close = 2
    link = 3
    noi = 4
    txt = 5

def old_tokenize(txt):
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


def new_tokenize(txt):
    import _expander

    if "<onlyinclude>" in txt:
        # if onlyinclude tags are used, only use text between those tags. template 'legend' is a example
        txt = "".join(onlyincluderx.findall(txt))
    
    txt=txt+u'\0'
    tokens = _expander.scan(txt)
    
    res = []
    for t in tokens:
        type,start,len=t
        if type:
            res.append((type, txt[start:start+len]))
        else:
            res.append((None, ''))
            
    
    return res

tokenize = old_tokenize



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

class Variable(Node):
    pass

class Template(Node):
    pass

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
        for idx, c in enumerate(children):
            if c==u'|':
                break
            name.children.append(c)


        # find the arguments
        

        arg = Node()

        linkcount = 0
        for idx, c in enumerate(children[idx+1:]):
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



class LazyArgument(object):
    def __init__(self, node, expander, variables):
        self.node = node
        self.expander = expander
        self._flatten = None
        self.variables = variables

    def flatten(self):
        if self._flatten is None:            
            arg=[]
            self.expander.flatten(self.node, arg, self.variables)

            arg = u"".join(arg).strip()

            self._flatten = arg
        return self._flatten

class ArgumentList(object):
    class notfound: pass

    def __init__(self):
        self.args = []
        self.namedargs = {}

    def append(self, a):
        self.args.append(a)

    def get(self, n, default):
        return self.__getitem__(n) or default

    def __iter__(self):
        for x in self.args:
            yield x

    def __getslice__(self, i, j):
        for x in self.args[i:j]:
            yield x.flatten()
        
    def __len__(self):
        return len(self.args)

    def __getitem__(self, n):
        if isinstance(n, (int, long)):
            try:
                a=self.args[n]
            except IndexError:
                return u""
            return a.flatten()

        assert isinstance(n, basestring), "expected int or string"

        varcount=1
        if n not in self.namedargs:
            for x in self.args:
                f=x.flatten()
                if u"=" in f:
                    name, val = f.split(u"=", 1)
                    name = name.strip()
                    val = val.strip()
                    self.namedargs[name] = val
                    if n==name:
                        return val
                else:
                    name = str(varcount)
                    varcount+=1
                    self.namedargs[name] = f

                    if n==name:
                        return f
            self.namedargs[n] = u''

        val = self.namedargs[n]

        return val
    
            
class Expander(object):
    def __init__(self, txt, pagename="", wikidb=None):
        assert wikidb is not None, "must supply wikidb argument in Expander.__init__"
        self.db = wikidb
        self.resolver = magics.MagicResolver(pagename=pagename)
        self.resolver.wikidb = wikidb

        self.parsed = Parser(txt).parse()
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
            # great hack:
            #   add zero byte to templates starting with a (semi)colon,
            #   and interpret zero byte + (semi)colon as EOLSTYLE
            if raw.startswith(":") or raw.startswith(";"):
                raw = '\x00'+raw
                
            log.info("parsing template", repr(name))
            res = Parser(raw).parse()
            
        self.parsedTemplateCache[name] = res
        return res
            
        
    def flatten(self, n, res, variables):
        if isinstance(n, Template):
            name = []
            self.flatten(n.children[0], name, variables)
            name = u"".join(name).strip()

            remainder = None
            if ":" in name:
                try_name, try_remainder = name.split(':', 1)
                if self.resolver.has_magic(try_name):
                    name=try_name
                    remainder = try_remainder

            var = ArgumentList()

            varcount = 1   #unnamed vars

            def args():
                if remainder is not None:
                    tmpnode=Node()
                    tmpnode.children.append(remainder)
                    yield tmpnode
                for x in n.children[1:]:
                    yield x

            for x in args():
                var.append(LazyArgument(x, self, variables))

            rep = self.resolver(name, var)

            if rep is not None:
                res.append(rep)
            else:            
                p = self.getParsedTemplate(name)
                if p:
                    self.flatten(p, res, var)
                
        elif isinstance(n, Variable):
            name = []
            self.flatten(n.children[0], name, variables)
            name = u"".join(name).strip()

            try:
                num = int(name)-1
            except ValueError:
                v = variables.get(name, None)
            else:
                v = variables.get(num, None)

            if v is None:
                if len(n.children)>1:
                    self.flatten(n.children[1:], res, variables)
                else:
                    pass
                    # FIXME. breaks If
                    #res.append(u"{{{%s}}}" % (name,))
            else:
                res.append(v)
        else:        
            for x in n:
                if isinstance(x, basestring):
                    res.append(x)
                else:
                    self.flatten(x, res, variables)

    def expandTemplates(self):
        res = []
        self.flatten(self.parsed, res, ArgumentList())
        return u"".join(res)


class DictDB(object):
    """wikidb implementation used for testing"""
    def __init__(self, *args, **kw):
        if args:
            self.d, = args
        else:
            self.d = {}
        
        self.d.update(kw)

    def getRawArticle(self, title):
        return self.d[title]

    def getTemplate(self, title, dummy):
        return self.d.get(title, u"")
    
def expandstr(s, expected=None, wikidb=None):
    """debug function. expand templates in string s"""
    if wikidb:
        db = wikidb
    else:
        db = DictDB(dict(a=s))

    te = Expander(s, pagename="thispage", wikidb=db)
    res = te.expandTemplates()
    print "EXPAND: %r -> %r" % (s, res)
    if expected:
        assert res==expected, "expected %r, got %r" % (expected, res)
    return res

if __name__=="__main__":
    #print splitrx.groupindex
    d=unicode(open(sys.argv[1]).read(), 'utf8')
    e = Expander(d)
    print e.expandTemplates()
