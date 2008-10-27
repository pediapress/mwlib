
# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.

from mwlib.templ.nodes import Node, Variable, Template
from mwlib.templ.scanner import symbols, tokenize

def optimize(node):
    if isinstance(node, basestring):
        return node

    if type(node) is Node and len(node.children)==1:
        return optimize(node.children[0])

    for i, x in enumerate(node.children):
        node.children[i] = optimize(x)
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
