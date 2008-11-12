from mwlib.templ import nodes, evaluate

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
        
registry = {'#time': Time}

