
import datetime
import re

from mwlib.templ import nodes, evaluate
from dateutil.parser import parse as parsedate

    
class Time(nodes.Node):
    rx = re.compile('"[^"]*"|.')
    codemap = dict(
        y = '%y',
        Y = '%Y',
        n = '%m', # FIXME: should not be zero padded
        m = '%m',
        M = '%b',
        F = '%B',
        W = '%U', # FIXME: need to add 1
        j = '%d', # FIXME: should not be zero-padded
        d = '%d',
        z = '%j',
        D = '%a',
        I = '%A',
        c = '%c',        
        )
    
    def flatten(self, expander, variables, res):
        format = []
        evaluate.flatten(self[0], expander, variables, format)
        format = u"".join(format).strip()
        #print "TIME-FORMAT:", format

        if len(self)>1:
            d = []
            evaluate.flatten(self[1], expander, variables, d)
            d = u"".join(d).strip()
            try:
                date = parsedate(d)
            except ValueError:
                return
        else:
            date = datetime.datetime.now()
        
        split = self.rx.findall(format)

        tmp = []
        for x in split:
            f = self.codemap.get(x, None)
            if f is None:
                tmp.append(x)
            else:
                tmp.append(date.strftime(f))

        tmp = u"".join(tmp).strip()
        res.append(tmp)
        
registry = {'#time': Time}

