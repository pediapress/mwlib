
# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.

from mwlib.templ import magics


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
    
    @property
    def descendants(self):
        """Iterator yielding all descendants of this Node which are Nodes"""
        
        for c in self.children:
            yield c
            if not isinstance(c, Node):
                continue
            for x in c.descendants:
                yield x        
    
    def find(self, tp):
        """Return instances of type tp in self.descendants"""
        
        return [x for x in self.descendants if isinstance(x, tp)]
    

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

def _switch_split_node(node):
    if isinstance(node, basestring):
        if '=' in node:
            return node.split("=", 1) #FIXME
        
        return None, node

    try:
        idx = node.children.index(u"=")
    except ValueError:
        #FIXME
        return None, node

    k = node.children[:idx]
    v = node.children[idx+1:]
    
    return k, v
    
        
        
class Template(Node):
    def flatten(self, expander, variables, res):
        try:
            return self._flatten(expander, variables, res)
        except RuntimeError, err:
            # we expect a "RuntimeError: maximum recursion depth exceeded" here.
            # logging this error is rather hard...
            try:
                log.warn("error %s ignored" % (err,))
            except:
                pass
            
        
    def _flatten(self, expander, variables, res):
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
                remainder=remainder.strip()
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
            elif name=='#ifeq':
                res.append(maybe_newline)
                tmp=[]
                if len(self.children)>=2:
                    flatten(self.children[1], expander, variables, tmp)
                other = u"".join(tmp).strip()
                remainder = remainder.strip()
                tmp = []
                if magics.maybe_numeric_compare(remainder, other):
                    if len(self.children)>=3:
                        flatten(self.children[2], expander, variables, tmp)
                        res.append(u"".join(tmp).strip())
                else:
                    if len(self.children)>=4:
                        flatten(self.children[3], expander, variables, tmp)
                        res.append(u"".join(tmp).strip())
                res.append(dummy_mark)
                return
            elif name=='#switch':
                res.append(maybe_newline)
                
                remainder = remainder.strip()
                default = None
                for i in xrange(1, len(self.children)):
                    c = self.children[i]
                    k, v = _switch_split_node(c)
                    if k is not None:
                        tmp = []
                        flatten(k, expander, variables, tmp)
                        k=u"".join(tmp).strip()

                    if k=='#default':
                        default = v
                        
                        
                    if (k is None and i==len(self.children)-1) or (k is not None and magics.maybe_numeric_compare(k, remainder)):
                        tmp = []
                        flatten(v, expander, variables, tmp)
                        v = u"".join(tmp).strip()
                        
                        res.append(v)
                        res.append(dummy_mark)
                        return

                if default is not None:
                    tmp=[]
                    flatten(default, expander, variables, tmp)
                    tmp = u"".join(tmp).strip()
                    res.append(tmp)
                    
                        
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
    import sys
    
    if out is None:
        out=sys.stdout

    out.write("%s%r\n" % ("  "*indent, node))
    if isinstance(node, basestring):
        return
    for x in node.children:
        show(x, indent+1, out)


from mwlib.templ.evaluate import maybe_newline, mark_start, mark_end, dummy_mark, flatten, MemoryLimitError, ArgumentList, LazyArgument
from mwlib.templ import log, DEBUG
