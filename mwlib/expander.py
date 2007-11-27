#! /usr/bin/env python

# Copyright (c) 2007, PediaPress GmbH
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
|((?:<noinclude>.*?</noinclude>)|(?:<!--.*?-->)|(?:</?includeonly>))  # noinclude, comments: usually ignore
|(?P<text>(?:<nowiki>.*?</nowiki>)          # nowiki
|(?:<math>.*?</math>)
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

def show(out, node, indent=0):
    print >>out, "  "*indent, node
    for x in node:
        if isinstance(x, basestring):
            print >>out, "  "*(indent+1), repr(x)
        else:
            show(out, x, indent+1)

def tokenize(txt):
    
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

class Node(object):
    def __init__(self):
        self.children = []

    def __repr__(self):
        return "<%s %s children>" % (self.__class__.__name__, len(self.children))

    def __iter__(self):
        for x in self.children:
            yield x
            
class Variable(Node):
    pass

class Template(Node):
    pass
    
class Backtrack(Exception):
    pass

class Parser(object):
    template_ns = set([ ((5, u'Template'), (5, u':')),
                        ((5, u'Vorlage'), (5, u':')),
                        ])


    def __init__(self, txt):
        self.txt = txt
        self.tokens = tokenize(txt)
        self.pos = 0
        self.changes = {}

    def _save(self):
        r = self.__dict__.copy()
        r['changes'] = self.changes.copy()
        return r

    def _restore(self, state):
        self.__dict__ = state
        
    def getToken(self):
        try:
            return self.changes[self.pos]
        except KeyError:
            return self.tokens[self.pos]

    def setToken(self, tok):
        self.changes[self.pos] = tok


    def parseVariable(self):
        v=Variable()
        n = Node()
        v.children.append(n)
        
        self.pos += 1

        while 1:
            ty, txt = self.getToken()
            if ty==symbols.bra_open:
                n.children.append(self.parseOpenBrace())
            elif ty==symbols.bra_close:
                if len(txt)>=3:
                    self._eatBrace(3)
                    break
                else:
                    raise Backtrack()
            elif ty==symbols.link:
                n.children.append(txt)
                self.pos += 1                
            elif ty==symbols.noi:
                self.pos += 1   # ignore <noinclude>
            elif ty==symbols.txt:
                self.pos += 1                
                if txt == '|' and n is not v:
                    n = v
                else:
                    n.children.append(txt)
            elif ty==None:
                raise Backtrack()
                break

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
        
        
    def parseTemplate(self):
        t = Template()
        n = Node()
        t.children.append(n)

        self.pos += 1
        ty, txt = self.getToken()

        if txt == ':':
            n.children.append(":")
            self.pos += 1
            
        if tuple(self.tokens[self.pos:self.pos+2]) in self.template_ns:
            self.pos += 2
            
            
        while 1:
            ty, txt = self.getToken()
            if ty==symbols.bra_open:
                n.children.append(self.parseOpenBrace())
            elif ty==symbols.bra_close:
                self._eatBrace(2)
                return t
            elif ty==symbols.link:
                n.children.append(txt)
                self.pos += 1       
            elif ty==symbols.noi:
                self.pos += 1   # ignore <noinclude>
            elif ty==symbols.txt:
                self.pos += 1
                if txt=='|' or txt==':':
                    break                
                n.children.append(txt)
            elif ty==None:
                raise Backtrack()

        n = Node()
        linkcount = 0   # count open braces...
        
        while 1:
            ty, txt = self.getToken()
            if ty==symbols.bra_open:
                n.children.append(self.parseOpenBrace())
            elif ty==symbols.bra_close:
                self._eatBrace(2)
                if n.children:
                    t.children.append(n)
                break
            elif ty==symbols.link:
                if txt=='[[':
                    linkcount += 1
                else:
                    linkcount -= 1                    
                n.children.append(txt)
                self.pos += 1
            elif ty==symbols.noi:
                self.pos += 1   # ignore <noinclude>
            elif ty==symbols.txt:
                if linkcount==0 and txt=='|':
                    t.children.append(n)
                    n = Node()
                else:
                    n.children.append(txt)
                self.pos += 1
                
            elif ty==None:
                break

        return t
    

    def parseOpenBrace(self):
        ty, txt = self.getToken()
        if len(txt)==2:
            try:
                state = self._save()
                return self.parseTemplate()
            except Backtrack:
                self._restore(state)
                n = Node()
                n.children.append("{{")
                self.pos += 1

                n.children.append(self.parse())
                return n
        
        if len(txt)>=3:
            try:
                state = self._save()
                return self.parseVariable()
            except Backtrack:
                self._restore(state)
                n = Node()
                n.children.append("{")
                self.setToken((ty, txt[1:]))
                n.children.append(self.parseOpenBrace())
                return n
            
        assert 0
            
        
    def parse(self):
        n = Node()
        while 1:
            ty, txt = self.getToken()
            if ty==symbols.bra_open:
                n.children.append(self.parseOpenBrace())
            elif ty==symbols.bra_close:
                n.children.append(txt)
                self.pos += 1
            elif ty==symbols.link:
                n.children.append(txt)
                self.pos += 1                
            elif ty==symbols.noi:
                self.pos += 1   # ignore <noinclude>
            elif ty==symbols.txt:
                n.children.append(txt)
                self.pos += 1
            elif ty==None:
                break
        return n


class Expander(object):
    def __init__(self, txt, pagename="", wikidb=None):
        assert wikidb is not None, "must supply wikidb argument in Expander.__init__"
        self.db = wikidb
        self.resolver = magics.MagicResolver(pagename=pagename)
        self.resolver.wikidb = wikidb

        self.parsed = Parser(txt).parse()
        #show(sys.stdout, self.parsed)
        self.variables = {}
        self.parsedTemplateCache = {}
        
    def getParsedTemplate(self, name):
        log.info("getParsedTemplate", repr(name))
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
            
        
    def flatten(self, n, res):
        if isinstance(n, Template):
            name = []
            self.flatten(n.children[0], name)
            name = u"".join(name).strip()


            var = {}
            varcount = 1
            for x in n.children[1:]:
                arg = []
                self.flatten(x, arg)
                arg = u"".join(arg)
                splitted = arg.split('=', 1)
                if len(splitted)>1:
                    if re.match("^(\w+|#default)$", splitted[0].strip()):
                        var[splitted[0].strip()] = splitted[1].strip()
                    else:
                        var[str(varcount)] = arg.strip()
                        varcount += 1
                else:
                    var[str(varcount)] = arg.strip()
                    varcount += 1
                    

            rep = self.resolver(name, var)
            if rep is not None:
                res.append(rep)
            else:            
                p = self.getParsedTemplate(name)
                if p:
                    oldvar = self.variables
                    self.variables = var
                    self.flatten(p, res)
                    self.variables = oldvar
                
        elif isinstance(n, Variable):
            name = []
            self.flatten(n.children[0], name)
            name = u"".join(name).strip()

            v = self.variables.get(name, None)
            if v is None:
                if len(n.children)>1:
                    self.flatten(n.children[1:], res)
                    
            else:
                res.append(v)
        else:        
            for x in n:
                if isinstance(x, basestring):
                    res.append(x)
                else:
                    self.flatten(x, res)

    def expandTemplates(self):
        res = []
        self.flatten(self.parsed, res)
        return u"".join(res)
    

if __name__=="__main__":
    #print splitrx.groupindex
    d=unicode(open(sys.argv[1]).read(), 'utf8')
    e = Expander(d)
    print e.expandTemplates()
    
