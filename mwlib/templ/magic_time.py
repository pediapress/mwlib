import sys
import datetime
import re
import calendar
import roman
from timelib import strtodatetime as parsedate

from mwlib.strftime import strftime

def ampm(date):
    if date.hour < 12:
        return "am"
    else:
        return "pm"

rx = re.compile('"[^"]*"|xr|\\\\.|.')
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
    xr = ("process_next", lambda n: roman.toRoman(int(n))),
    )


def formatdate(format, date):
    split = rx.findall(format)
    process_next = None

    tmp = []
    for x in split:
        f = codemap.get(x, None)
        if f is None:
            if len(x)==2 and x.startswith("\\"):
                tmp.append(x[1])
            elif len(x)>=2 and x.startswith('"'):
                tmp.append(x[1:-1])
            else:
                tmp.append(x)
        else:
            if isinstance(f, tuple):
                process_next = f[1]
                continue

            if isinstance(f, basestring):
                res = strftime(date, f)
            else:
                res = f(date)

            if process_next:
                try:
                    res = process_next(res)
                except ValueError:
                    pass
                process_next = None
            tmp.append(res)

    tmp = u"".join(tmp).strip()
    return tmp

def time(format, datestring=None):
    date = None
    if datestring:
        if re.match("\d\d\d\d$", datestring):
            try:
                date = datetime.datetime.now().replace(hour=int(datestring[:2]), minute=int(datestring[2:]), second=0)
            except ValueError:
                pass
        
        if date is None:
            try:
                date = parsedate(datestring)
            except ValueError:
                pass
            except Exception, err:
                sys.stderr.write("ERROR in parsedate: %r while parsing %r" % (err, datestring))
                pass

        if date is None:
            return  u'<strong class="error">Error: invalid time</strong>'
        
    if date is None:
        date = datetime.datetime.now()

    return formatdate(format, date)
