
# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.

from mwlib.templ import magics, log, DEBUG
from mwlib.templ import parser

def flatten(node, expander, variables, res):
    before = variables.count
    t=type(node)
    if t is unicode or t is str:
        res.append(node)
    elif t is list:
        for x in node:
            flatten(x, expander, variables, res)
    else:
        node.flatten(expander, variables, res)
    after = variables.count
    return before==after


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
                from mwlib.templ import nodes
                val = nodes.Node()
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
        self.count = 0
        
    def __repr__(self):
        return "<ARGLIST args=%r>" % ([x.flatten() for x in self.args],)
    
    def append(self, a):
        self.count += 1
        self.args.append(a)

    def __iter__(self):
        self.count += 1
        for x in self.args:
            yield x

    def __getslice__(self, i, j):
        self.count += 1
        for x in self.args[i:j]:
            yield x.flatten()
        
    def __len__(self):
        self.count += 1
        return len(self.args)

    def __getitem__(self, n):
        self.count += 1
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

        self.parsed = parser.parse(txt)
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
            res = parser.parse(raw)
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
