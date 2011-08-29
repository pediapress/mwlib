from xml.sax.saxutils import quoteattr
from mwlib.templ import nodes, evaluate

class Subst(nodes.Node):
    def flatten(self, expander, variables, res):
        name = []
        evaluate.flatten(self[0], expander, variables, name)
        name = u"".join(name).strip()
        
        res.append("{{subst:%s}}" % (name,))

class Safesubst(nodes.Template):
    def _get_args(self):
        return self[1:]


class Time(nodes.Node):
    def flatten(self, expander, variables, res):
        format = []
        evaluate.flatten(self[0], expander, variables, format)
        format = u"".join(format).strip()


        
        if len(self)>1:
            d = []
            evaluate.flatten(self[1], expander, variables, d)
            d = u"".join(d).strip()
        else:
            d = None

        from mwlib.templ import magic_time
        res.append(magic_time.time(format, d))

class Anchorencode(nodes.Node):
    def flatten(self, expander, variables, res):
        arg = []
        evaluate.flatten(self[0], expander, variables, arg)
        arg = u"".join(arg)

        # Note: mediawiki has a bug. It tries not to touch colons by replacing '.3A' with
        # with the colon. However, if the original string contains the substring '.3A',
        # it will also replace it with a colon. We do *not* reproduce that bug here...
        import urllib
        e = urllib.quote_plus(arg.encode('utf-8'), ':').replace('%', '.').replace('+', '_')
        res.append(e)

def _rel2abs(rel, base):
    rel=rel.rstrip("/")
    if rel in (u"", "."):
        return base
    if not (rel.startswith("/") or rel.startswith("./") or rel.startswith("../")):
        base = u""

    import posixpath
    p = posixpath.normpath("/%s/%s/" % (base, rel)).strip("/")
    return p

    
class rel2abs(nodes.Node):
    def flatten(self, expander, variables, res):
        arg = []
        evaluate.flatten(self[0], expander, variables, arg)
        arg = u"".join(arg).strip()

        arg2 = []
        if len(self)>1:
            evaluate.flatten(self[1], expander, variables, arg2)
        arg2 = u"".join(arg2).strip()
        if not arg2:
            arg2 = expander.pagename

        res.append(_rel2abs(arg, arg2))
        
class Tag(nodes.Node):
    def flatten(self, expander, variables, res):
        name = []
        evaluate.flatten(self[0], expander, variables, name)
        name = u"".join(name).strip()
        parameters = u''

        for parm in self[2:]:
            tmp = []
            evaluate.flatten(parm, expander, variables, tmp)
            evaluate._insert_implicit_newlines(tmp)
            tmp = u"".join(tmp)
            if "=" in tmp:
                key, value = tmp.split("=", 1)
                parameters += " %s=%s" % (key, quoteattr(value))

        tmpres = []
        tmpres.append("<%s%s>" % (name, parameters))
        
        if len(self)>1:
            tmp = []
            evaluate.flatten(self[1], expander, variables, tmp)
            evaluate._insert_implicit_newlines(tmp)
            tmp = u"".join(tmp)
            tmpres.append(tmp)
            
        tmpres.append("</%s>" % (name,))
        tmpres = u"".join(tmpres)
        tmpres = expander.uniquifier.replace_tags(tmpres)
        res.append(tmpres)
        
        

class NoOutput(nodes.Node):
    def flatten(self, expander, variables, res):
        pass

class Defaultsort(NoOutput):
    pass

class Displaytitle(nodes.Node):
    def flatten(self, expander, variables, res):
        name = []
        evaluate.flatten(self[0], expander, variables, name)
        name = u"".join(name).strip()
        expander.magic_displaytitle = name
        

def make_switchnode(args):
    return nodes.SwitchNode((args[0], args[1:]))

registry = {'#time': Time,
            'subst': Subst,
            'safesubst': Safesubst,
            'anchorencode': Anchorencode,
            '#tag': Tag,
            'displaytitle': Displaytitle,
            'defaultsort': Defaultsort,
            '#rel2abs': rel2abs,
            '#switch': make_switchnode, 
            '#if': nodes.IfNode,
            '#ifeq': nodes.IfeqNode,
            }
