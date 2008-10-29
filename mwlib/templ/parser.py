
# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.

from mwlib.templ.nodes import Node, Variable, Template
from mwlib.templ.scanner import symbols, tokenize

def optimize(node):
    if isinstance(node, tuple):
        return node
    
    if isinstance(node, basestring):
        return node

    if len(node)==1 and type(node) in (list, Node):
        return optimize(node[0])

    if isinstance(node, (Variable, Template)):
        for i, x in enumerate(node):
            node[i] = optimize(x)
    else:
        # combine strings
        res = []
        tmp = []
        for x in (optimize(x) for x in node):
            if isinstance(x, basestring) and x!='=':
                tmp.append(x)
            else:
                if tmp:
                    res.append(u''.join(tmp))
                    tmp = []
                res.append(x)
        if tmp:
            res.append(u''.join(tmp))

        node[:] = res
    
    
    if len(node)==1 and type(node) in (list, Node):
        return optimize(node[0])
    
    return node

    
class Parser(object):
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
        

        try:
            idx = children.index(u"|")
        except ValueError:
            v.append(children)
        else:
            v.append(children[:idx])
            v.append(children[idx+1:])

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
        t.append(name)
        
        idx = 0
        for idx, c in enumerate(children):
            if c==u'|':
                break
            name.append(c)


        # find the arguments
        args = []
        

        arg = Node()

        linkcount = 0
        for c in children[idx+1:]:
            if c==u'[[':
                linkcount += 1
            elif c==']]':
                linkcount -= 1
            elif c==u'|' and linkcount==0:
                args.append(arg)
                arg = Node()
                continue
            arg.append(c)


        if arg:
            args.append(arg)

        args = [optimize(x) for x in args]
        
        t.append(tuple(args))
        #t.append(args)

        return t
        
    def parseOpenBrace(self):
        ty, txt = self.getToken()
        n = Node()

        numbraces = len(txt)
        self.pos += 1
        
        while 1:
            ty, txt = self.getToken()
            if ty==symbols.bra_open:
                n.append(self.parseOpenBrace())
            elif ty is None:
                break
            elif ty==symbols.bra_close:
                closelen = len(txt)
                if closelen==2 or numbraces==2:
                    t=self.templateFromChildren(n)
                    n=Node()
                    n.append(t)
                    self._eatBrace(2)
                    numbraces-=2
                else:
                    v=self.variableFromChildren(n)
                    n=Node()
                    n.append(v)
                    self._eatBrace(3)
                    numbraces -= 3

                if numbraces==0:
                    break
                elif numbraces==1:
                    n.insert(0, "{")
                    break
            elif ty==symbols.noi:
                self.pos += 1 # ignore <noinclude>
            else: # link, txt
                n.append(txt)
                self.pos += 1                

        return n
        
    def parse(self):
        n = Node()
        while 1:
            ty, txt = self.getToken()
            if ty==symbols.bra_open:
                n.append(self.parseOpenBrace())
            elif ty is None:
                break
            elif ty==symbols.noi:
                self.pos += 1   # ignore <noinclude>
            else: # bra_close, link, txt                
                n.append(txt)
                self.pos += 1
        return n

def parse(txt):
    return optimize(Parser(txt).parse())
