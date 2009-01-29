from mwlib.templ import nodes, evaluate

class Subst(nodes.Node):
    def flatten(self, expander, variables, res):
        name = []
        evaluate.flatten(self[0], expander, variables, name)
        name = u"".join(name).strip()
        
        res.append("{{subst:%s}}" % (name,))

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

class Tag(nodes.Node):
    def flatten(self, expander, variables, res):
        name = []
        evaluate.flatten(self[0], expander, variables, name)
        name = u"".join(name).strip()

        res.append("<%s>" % (name,))
        
        if len(self)>1:
            tmp = []
            evaluate.flatten(self[1], expander, variables, tmp)
            evaluate._insert_implicit_newlines(tmp)
            tmp = u"".join(tmp)
            res.append(tmp)
            
        res.append("</%s>" % (name,))
        

class NoOutput(nodes.Node):
    def flatten(self, expander, variables, res):
        pass

class Defaultsort(NoOutput):
    pass

class Displaytitle(NoOutput):
    pass

registry = {'#time': Time,
            'subst': Subst,
            'anchorencode': Anchorencode,
            '#tag': Tag,
            'displaytitle': Displaytitle,
            'defaultsort': Defaultsort,
            }
