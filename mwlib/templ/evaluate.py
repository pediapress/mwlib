
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.txt for additional licensing information.

import re
from mwlib.templ import magics, log, DEBUG, parser, mwlocals


class TemplateRecursion(Exception): pass

def flatten(node, expander, variables, res):
    t=type(node)
    if t is unicode or t is str:
        res.append(node)
        return True

    if expander.recursion_count > expander.recursion_limit:
        raise TemplateRecursion()
    
    
    expander.recursion_count += 1
    try:
        before = variables.count
        oldlen = len(res)
        try:
            if t is list or t is tuple:
                for x in node:
                    flatten(x, expander, variables, res)
            else:
                node.flatten(expander, variables, res)
        except TemplateRecursion:
            if expander.recursion_count > 2:
                raise
            del res[oldlen:]
            log.warn("template recursion error ignored")
        after = variables.count
        return before==after
    finally:
        expander.recursion_count -= 1
        
        
class MemoryLimitError(Exception):
    pass


def equalsplit(node):
    if isinstance(node, basestring):
        if '=' in node:
            return node.split('=', 1)
        else:
            return None, node

    try:
        idx = node.index(u'=')
    except ValueError:
        return None, node

    return node[:idx], node[idx+1:]

    
def equalsplit_25(node):
    if isinstance(node, basestring):
        if '=' in node:
            return node.split('=', 1)
        else:
            return None, node

    try:
        idx = list(node).index(u'=')
    except ValueError:
        return None, node

    return node[:idx], node[idx+1:]
    
if not hasattr(tuple, 'index'):
    equalsplit = equalsplit_25

class ArgumentList(object):
    def __init__(self, args=tuple(), expander=None, variables=None):
        self.args = tuple(args)
        

        assert expander is not None
        #assert variables is not None
        
        self.expander = expander
        self.variables = variables
        self.varcount = 1
        self.varnum = 0
        
        self.namedargs = {}
        self.count = 0
            
    def __len__(self):
        self.count += 1
        return len(self.args)

    def __getitem__(self, n):
        self.count += 1
        return self.get(n, None) or u''
        
    def get(self, n, default):
        self.count += 1
        if isinstance(n, (int, long)):
            try:
                a=self.args[n]
            except IndexError:
                return default
            if isinstance(a, unicode):
                return a.strip()
            tmp = []
            flatten(a, self.expander, self.variables, tmp)
            _insert_implicit_newlines(tmp)
            tmp = u"".join(tmp).strip()
            if len(tmp)>256*1024:
                raise MemoryLimitError("template argument too long: %s bytes" % len(tmp))
            # FIXME: cache value ???
            return tmp

        assert isinstance(n, basestring), "expected int or string"

        if n not in self.namedargs:
            while self.varnum < len(self.args):
                arg = self.args[self.varnum]
                self.varnum += 1

                name, val = equalsplit(arg)
                if name is not None:
                    tmp = []
                    flatten(name, self.expander, self.variables, tmp)
                    _insert_implicit_newlines(tmp)
                    name = u"".join(tmp).strip()
                else:
                    name = str(self.varcount)
                    self.varcount+=1
                
                self.namedargs[name] = val
                
                if n==name:
                    break

        try:
            val = self.namedargs[n]
            if isinstance(val, unicode):
                return val
        except KeyError:
            return default

        tmp = []
        flatten(val, self.expander, self.variables, tmp)
        _insert_implicit_newlines(tmp)
        tmp=u"".join(tmp).strip()
        self.namedargs[n] = tmp
        return tmp
    
def is_implicit_newline(raw):
    """should we add a newline to templates starting with *, #, :, ;, {|
    see: http://meta.wikimedia.org/wiki/Help:Newlines_and_spaces#Automatic_newline_at_the_start
    """
    sw = raw.startswith
    for x in ('*', '#', ':', ';', '{|'):
        if sw(x):
            return True
    return False 

from mwlib.templ.marks import mark, mark_start, mark_end, mark_maybe_newline, maybe_newline, dummy_mark

def _insert_implicit_newlines(res, maybe_newline=maybe_newline):
    # do not pass the second argument
    res.append(dummy_mark)
    res.append(dummy_mark)

    for i, p in enumerate(res):
        if p is maybe_newline:
            s1 = res[i+1]
            s2 = res[i+2]
            if i and res[i-1].endswith("\n"):
                continue
            
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
    random_string = None 
    def __init__(self, txt, pagename="", wikidb=None, recursion_limit=100):
        assert wikidb is not None, "must supply wikidb argument in Expander.__init__"
        self.pagename = pagename
        self.db = wikidb
        self.uniq2repl = {}
        
        if self.db and hasattr(self.db, "getSource"):
            source = self.db.getSource(pagename) or {}
            local_values = source.get("locals", u"")
            local_values = mwlocals.parse_locals(local_values)
        else:
            local_values = None
            
            
        self.resolver = magics.MagicResolver(pagename=pagename)
        self.resolver.wikidb = wikidb
        self.resolver.local_values = local_values
        
        self.recursion_limit = recursion_limit
        self.recursion_count = 0

        self.parsed = parser.parse(txt, included=False, replace_tags=self.replace_tags)
        #show(self.parsed)
        self.parsedTemplateCache = {}

    def _repl_from_uniq(self, mo):
        u = mo.group(0)
        return self.uniq2repl.get(u, u)

    def replace_uniq(self, txt):
        
        rx=re.compile(r"UNIQ-\d+-[a-f0-9]+-QINU")
        txt = rx.sub(self._repl_from_uniq, txt)
        return txt
    
        
        
    def _repl_to_uniq(self, mo):
        return self.get_uniq(mo.group(0))
    
    def replace_tags(self, txt):
        
        rx=re.compile("""(?:<nowiki>.*?</nowiki>)          # nowiki
|(?:<math>.*?</math>)
|(?:<imagemap[^<>]*>.*?</imagemap>)
|(?:<gallery[^<>]*>.*?</gallery>)
|(?:<ref[^<>]*/?>)
|(?:<source[^<>]*>.*?</source>)
|(?:<pre.*?>.*?</pre>)""", re.VERBOSE | re.DOTALL | re.IGNORECASE)
        newtxt = rx.sub(self._repl_to_uniq, txt)
        return newtxt

    def get_uniq(self, repl):
        r = self.get_random_string()
        count = len(self.uniq2repl)
        retval = "UNIQ-%s-%s-QINU" % (count, r)
        self.uniq2repl[retval] = repl
        return retval
    
        
    def get_random_string(self):
        if self.random_string is None:
            import binascii
            r=open("/dev/urandom").read(8)
            self.__class__.random_string = binascii.hexlify(r)
        return self.random_string

    def getParsedTemplate(self, name):
        if name.startswith("[[") or "|" in name:
            return None

        if name.startswith("/"):
            name = self.pagename+name
            
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
            res = parser.parse(raw, replace_tags=self.replace_tags)
            if DEBUG:
                print "TEMPLATE:", name, repr(raw)
                #res.show()
                
        self.parsedTemplateCache[name] = res
        return res
            
        
    def expandTemplates(self):
        res = ["\n"] # guard, against implicit newlines at the beginning
        flatten(self.parsed, self, ArgumentList(expander=self), res)
        _insert_implicit_newlines(res)
        res[0] = u''
        res = u"".join(res)
        res=self.replace_uniq(res)
        return res
