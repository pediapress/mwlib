
import datetime
import re

from mwlib.templ import nodes, evaluate
from dateutil.parser import parse as parsedate
import calendar

def ampm(date):
    if date.hour < 12:
        return "am"
    else:
        return "pm"

class Time(nodes.Node):
    rx = re.compile('"[^"]*"|\\\\.|.')
    codemap = dict(
        y = '%y',
        Y = '%Y',
        n = lambda d: str(d.month),
        m = '%m',
        M = '%b',
        F = '%B',
        W = lambda d: "%02d" % (d.isocalendar()[1],),
        j = lambda d: str(d.day),
        d = '%d',
        z = lambda d: str(d.timetuple().tm_yday-1),
        D = '%a',
        l = '%A',
        N = lambda d: str(d.isoweekday()),
        w = lambda d: str(d.isoweekday() % 7),
        a = ampm,
        A = lambda d: ampm(d).upper(),
        g = lambda d: str(((d.hour-1) % 12) + 1),
        h = "%I",
        G = lambda d: str(d.hour),
        H = lambda d: "%02d" % (d.hour,),
        i = '%M',
        s = '%S',
        U = lambda d: str(calendar.timegm(d.timetuple())),
        L = lambda d: str(int(calendar.isleap(d.year))),
        c = "%Y-%m-%dT%H:%M:%S+00:00",
        r = "%a, %d %b %Y %H:%M:%S +0000",
        t = lambda d: str(calendar.monthrange(d.year, d.month)[1]),
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
                if len(x)==2 and x.startswith("\\"):
                    tmp.append(x[1])
                elif len(x)>=2 and x.startswith('"'):
                    tmp.append(x[1:-1])
                else:
                    tmp.append(x)
            else:
                if isinstance(f, basestring):
                    tmp.append(date.strftime(f))
                else:
                    tmp.append(f(date))
                    

        tmp = u"".join(tmp).strip()
        res.append(tmp)
        
registry = {'#time': Time}

