
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

from mwlib.templ import magics, log, DEBUG, parser, mwlocals
from mwlib.uniq import Uniquifier
from mwlib import nshandling, siteinfo, metabook

class TemplateRecursion(Exception): pass

def flatten(node, expander, variables, res):
    t=type(node)
    if isinstance(node, (unicode, str)):
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
        return None, node

    try:
        idx = node.index(eqmark)
    except ValueError:
        return None, node

    return node[:idx], node[idx+1:]

    
def equalsplit_25(node):
    if isinstance(node, basestring):
        return None, node

    try:
        idx = list(node).index(eqmark)
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
        if isinstance(n, slice):
            start = n.start or 0
            stop = n.stop or len(self)
            return [self.get(x,  None) or u"" for x in range(start, stop)]
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
                    do_strip = True
                else:
                    name = str(self.varcount)
                    self.varcount+=1
                    do_strip = False

                if do_strip and isinstance(val, unicode):
                    val = val.strip()
                self.namedargs[name] = (do_strip, val)
                
                if n==name:
                    break

        try:
            do_strip, val = self.namedargs[n]
            if isinstance(val, unicode):
                return val
        except KeyError:
            return default

        tmp = []
        flatten(val, self.expander, self.variables, tmp)
        _insert_implicit_newlines(tmp)
        tmp=u"".join(tmp)
        if do_strip:
            tmp = tmp.strip()
            
        self.namedargs[n] = (do_strip, tmp)
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

from mwlib.templ.marks import mark, mark_start, mark_end, mark_maybe_newline, maybe_newline, dummy_mark, eqmark

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
    magic_displaytitle = None   # set via {{DISPLAYTITLE:...}}
    def __init__(self, txt, pagename="", wikidb=None, recursion_limit=100):
        assert wikidb is not None, "must supply wikidb argument in Expander.__init__"
        self.pagename = pagename
        self.db = wikidb
        self.uniquifier = Uniquifier()

        si = None
        try:
            si = self.db.get_siteinfo()
        except Exception, err:
            print 'Caught: %s' % err

        if si is None:
            print "WARNING: failed to get siteinfo from %r" % (self.db,)
            si = siteinfo.get_siteinfo("de")
            
        self.nshandler = nshandler = nshandling.nshandler(si)
        self.siteinfo = si

        if self.db and hasattr(self.db, "getSource"):
            source = self.db.getSource(pagename) or metabook.source()
            local_values = source.locals or u""
            local_values = mwlocals.parse_locals(local_values)
        else:
            local_values = None
            source = {}
            
        self.resolver = magics.MagicResolver(pagename=pagename)
        self.resolver.siteinfo = si
        self.resolver.nshandler = nshandler
        
        self.resolver.wikidb = wikidb
        self.resolver.local_values = local_values
        self.resolver.source = source
        
        self.recursion_limit = recursion_limit
        self.recursion_count = 0
        self.aliasmap = parser.aliasmap(self.siteinfo)

        self.parsed = parser.parse(txt, included=False, replace_tags=self.replace_tags, siteinfo=self.siteinfo)
        #show(self.parsed)
        self.parsedTemplateCache = {}

    def resolve_magic_alias(self, name):
        return self.aliasmap.resolve_magic_alias(name)

    def replace_tags(self, txt):
        return self.uniquifier.replace_tags(txt)
        
    def getParsedTemplate(self, name):
        if not name or name.startswith("[[") or "|" in name:
            return None


        if name.startswith("/"):
            name = self.pagename+name
            ns = 0
        else:
            ns = 10

        try:
            return self.parsedTemplateCache[name]
        except KeyError:
            pass

        page = self.db.normalize_and_get_page(name, ns)
        if page:
            raw = page.rawtext
        else:
            raw = None
            
        if raw is None:
            res = None
        else:
            res = self._parse_raw_template(name=name, raw=raw)
                
        self.parsedTemplateCache[name] = res
        return res

    def _parse_raw_template(self, name, raw):
        return parser.parse(raw, replace_tags=self.replace_tags)
    
    def _expand(self, parsed, keep_uniq=False):
        res = ["\n"] # guard, against implicit newlines at the beginning
        flatten(parsed, self, ArgumentList(expander=self), res)
        _insert_implicit_newlines(res)
        res[0] = u''
        res = u"".join(res)
        if not keep_uniq:
            res=self.uniquifier.replace_uniq(res)
        return res
        
    def parseAndExpand(self, txt, keep_uniq=False):
        parsed = parser.parse(txt, included=False, replace_tags=self.replace_tags)
        return self._expand(parsed, keep_uniq=keep_uniq)
    
    def expandTemplates(self, keep_uniq=False):
        return self._expand(self.parsed, keep_uniq=keep_uniq)
