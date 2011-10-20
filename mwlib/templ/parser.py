
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

import re
from mwlib.templ.nodes import Node, Variable, Template, IfNode, SwitchNode
from mwlib.templ.scanner import symbols, tokenize
from mwlib.templ.marks import eqmark

from hashlib import sha1 as digest

class aliasmap(object):
    def __init__(self, siteinfo):
        _map = {}
        _name2aliases = {}

        for d in siteinfo.get("magicwords", []):
            name = d["name"]
            aliases = d["aliases"]
            _name2aliases[name] = aliases
            hashname = "#" + name
            for a in aliases:
                _map[a] = name
                _map["#"+a] = hashname

        self._map = _map
        self._name2aliases = _name2aliases

    def resolve_magic_alias(self, name):
        if name.startswith("#"):
            t = self._map.get(name[1:])
            if t:
                return "#" + t
        else:
            return self._map.get(name)

    def get_aliases(self, name):
        return self._name2aliases.get(name) or []


def optimize(node):
    if type(node) is tuple:
        return tuple(optimize(x) for x in node)
    
    if isinstance(node, basestring):
        return node

    if len(node)==1 and type(node) in (list, Node):
        return optimize(node[0])

    if isinstance(node, Node): #(Variable, Template, IfNode)):
        return node.__class__(tuple(optimize(x) for x in node))
    else:
        # combine strings
        res = []
        tmp = []
        for x in (optimize(x) for x in node):
            if isinstance(x, basestring) and x is not eqmark:
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

    if type(node) is list:
        return tuple(node)
        
    return node

from mwlib import lrucache

class Parser(object):
    use_cache = False
    _cache = lrucache.mt_lrucache(2000)
    
    def __init__(self, txt, included=True, replace_tags=None, siteinfo=None):
        if isinstance(txt, str):
            txt = unicode(txt)
            
        self.txt = txt
        self.included = included
        self.replace_tags = replace_tags
        if siteinfo is None:
            from mwlib.siteinfo import get_siteinfo
            siteinfo = get_siteinfo("en")
        self.siteinfo = siteinfo
        self.name2rx = {"if": re.compile("^#if:"),
                        "switch": re.compile("^#switch:")}


        magicwords = self.siteinfo.get("magicwords", [])
        for d in magicwords:
            name = d["name"]
            if name in ("if", "switch"):
                aliases = [re.escape(x) for x in d["aliases"]]
                rx = "^#(%s):" % ("|".join(aliases),)
                self.name2rx[name] = re.compile(rx)
                # print name, rx

        self.aliasmap = aliasmap(self.siteinfo)

    def getToken(self):
        return self.tokens[self.pos]

    def setToken(self, tok):
        self.tokens[self.pos] = tok


    def variableFromChildren(self, children):
        v=[]

        try:
            idx = children.index(u"|")
        except ValueError:
            v.append(children)
        else:
            v.append(children[:idx])
            v.append(children[idx+1:])

        return Variable(v)
        
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

    def _strip_ws(self, cond):
        if isinstance(cond, unicode):
            return cond.strip()

        cond = list(cond)
        if cond and isinstance(cond[0], unicode):
            if not cond[0].strip():
                del cond[0]

        if cond and isinstance(cond[-1], unicode):
            if not cond[-1].strip():
                del cond[-1]
        cond = tuple(cond)
        return cond
    
    def switchnodeFromChildren(self, children):
        children[0] = children[0].split(":", 1)[1]
        args = self._parse_args(children)
        value = optimize(args[0])
        value = self._strip_ws(value)
        return SwitchNode((value, tuple(args[1:])))
        
    def ifnodeFromChildren(self, children):
        children[0] = children[0].split(":", 1)[1]
        args = self._parse_args(children)
        cond = optimize(args[0])
        cond = self._strip_ws(cond)
        
        args[0] = cond
        n = IfNode(tuple(args))
        return n

    def magicNodeFromChildren(self, children, klass):
        children[0] = children[0].split(":", 1)[1]
        args = self._parse_args(children)
        return klass(args)
    
    def _parse_args(self, children, append_arg=False):
        args = []
        arg = []

        linkcount = 0
        for c in children:
            if c==u'[[':
                linkcount += 1
            elif c==']]':
                if linkcount:
                    linkcount -= 1
            elif c==u'|' and linkcount==0:
                args.append(arg)
                arg = []
                append_arg = True
                continue
            elif c==u"=" and linkcount==0:
                arg.append(eqmark)
                continue
            arg.append(c)


        if append_arg or arg:
            args.append(arg)

        return [optimize(x) for x in args]

    def _is_good_name(self, node):

        # we stop here on the first colon. this is wrong but we don't have
        # the list of allowed magic functions here...
        done = False
        if isinstance(node, basestring):
            node = [node]
            
        for x in node:
            if not isinstance(x, basestring):
                continue
            if ":" in x:
                x = x.split(":")[0]
                done=True
                
            if "[" in x or "]" in x:
                return False
            if done:
                break
        return True
    
    def templateFromChildren(self, children):
        if children and isinstance(children[0], unicode):
            s = children[0].strip().lower()
            if self.name2rx["if"].match(s):
                return self.ifnodeFromChildren(children)
            if self.name2rx["switch"].match(s):
                return self.switchnodeFromChildren(children)
            
            if u':' in s:
                from mwlib.templ import magic_nodes
                name, first = s.split(':', 1)
                name = self.aliasmap.resolve_magic_alias(name) or name
                if name in magic_nodes.registry:
                    return self.magicNodeFromChildren(children, magic_nodes.registry[name])
                
                
            
        # find the name
        name = []
        append_arg = False
        idx = 0
        for idx, c in enumerate(children):
            if c==u'|':
                append_arg = True
                break
            name.append(c)

        name = optimize(name)
        if isinstance(name, unicode):
            name = name.strip()

        if not self._is_good_name(name):
            return Node([u"{{"] + children + [u"}}"])
        
        args = self._parse_args(children[idx+1:], append_arg=append_arg)
        
        return Template([name, tuple(args)])
        
    def parseOpenBrace(self):
        ty, txt = self.getToken()
        n = []

        numbraces = len(txt)
        self.pos += 1

        linkcount = 0
        
        while 1:
            ty, txt = self.getToken()

            if ty==symbols.bra_open:
                n.append(self.parseOpenBrace())
            elif ty is None:
                break
            elif ty==symbols.bra_close and linkcount==0:
                closelen = len(txt)
                if closelen==2 or numbraces==2:
                    t=self.templateFromChildren(n)
                    n=[]
                    n.append(t)
                    self._eatBrace(2)
                    numbraces-=2
                else:
                    v=self.variableFromChildren(n)
                    n=[]
                    n.append(v)
                    self._eatBrace(3)
                    numbraces -= 3

                if numbraces < 2:
                    break
            elif ty==symbols.noi:
                self.pos += 1 # ignore <noinclude>
            else: # link, txt
                if txt=="[[":
                    linkcount += 1
                elif txt=="]]" and linkcount>0:
                    linkcount -= 1

                n.append(txt)
                self.pos += 1            

        if numbraces:
            n.insert(0, "{"*numbraces)
            
        return n
        
    def parse(self):
        if self.use_cache:
            fp = digest(self.txt.encode('utf-8')).digest()     
            try:
                return self._cache[fp]
            except KeyError:
                pass
        
        
        self.tokens = tokenize(self.txt, included=self.included, replace_tags=self.replace_tags)
        self.pos = 0
        n = []
        
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

        n=optimize(n)
        
        if self.use_cache:
            self._cache[fp] = n
        
        return n

def parse(txt, included=True, replace_tags=None, siteinfo=None):
    return Parser(txt, included=included, replace_tags=replace_tags, siteinfo=siteinfo).parse()
