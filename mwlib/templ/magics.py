#! /usr/bin/env python

# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

"""expand magic variables/colon functions
http://meta.wikimedia.org/wiki/Help:Colon_function
http://meta.wikimedia.org/wiki/Help:Magic_words
http://meta.wikimedia.org/wiki/ParserFunctions
"""

import re
import datetime
import urllib
import urlparse
from mwlib.log import Log
from mwlib import expr

iferror_rx = re.compile(r'<(div|span|p|strong)\s([^<>]*\s)*?class="error"[^<>]*>', re.I)

log = Log("expander")

def singlearg(fun):
    def wrap(self, args):
        rl=args
        if not rl:
            a=u''
        else:
            a=rl[0]

        return fun(self, a)

    return wrap

def noarg(fun):
    def wrap(self, *args):
        return fun(self)
    return wrap

def as_numeric(x):
    try:
        return int(x)
    except ValueError:
        pass
    return float(x)


def maybe_numeric_compare(a,b):
    if a==b:
        return True
    try:
        try:
            a=int(a)
        except ValueError:
            a=float(a)
        try:
            b=int(b)
        except ValueError:
            b=float(b)
    except ValueError:
        return False

    return a==b

def urlquote(u):
    if isinstance(u, unicode):
        u = u.encode('utf-8')
    return urllib.quote(u)

class OtherMagic(object):
    def DEFAULTSORT(self, args):
        """see http://en.wikipedia.org/wiki/Template:DEFAULTSORT"""
        return u""


class TimeMagic(object):
    utcnow = datetime.datetime.utcnow()

    @noarg
    def CURRENTDAY(self):
        """Displays the current day in numeric form."""
        return "%s" % self.utcnow.day

    @noarg
    def CURRENTDAY2(self):
        """[MW1.5+] Ditto with leading zero 01 .. 31)."""
        return "%02d" % self.utcnow.day

    @noarg
    def CURRENTDAYNAME(self):
        """Displays the current day in named form."""
        return self.utcnow.strftime("%A")

    @noarg
    def CURRENTDOW(self):
        """current day as number (0=Sunday, 1=Monday...)."""
        return str((self.utcnow.weekday()+1) % 7)

    @noarg
    def CURRENTMONTH(self):
        """The number 01 .. 12 of the current month."""
        return "%02d" % self.utcnow.month

    @noarg
    def CURRENTMONTHABBREV(self):
        """[MW1.5+] current month abbreviated Jan .. Dec."""
        return self.utcnow.strftime("%b")

    @noarg        
    def CURRENTMONTHNAME(self):
        """current month in named form January .. December.   """
        return self.utcnow.strftime("%B")

    @noarg
    def CURRENTTIME(self):
        """The current time of day (00:00 .. 23:59)."""
        return self.utcnow.strftime("%H:%M")

    @noarg
    def CURRENTWEEK(self):
        """Number of the current week (1-53) according to ISO 8601 with no leading zero."""
        return str(self.utcnow.isocalendar()[1])

    @noarg
    def CURRENTYEAR(self):
        """Returns the current year."""
        return str(self.utcnow.year)

    @noarg
    def CURRENTTIMESTAMP(self):
        """[MW1.7+] Returns the current time stamp. e.g.: 20060528125203"""
        return self.utcnow.strftime("%Y%m%d%H%M%S")
    
class LocaltimeMagic(object):
    now = datetime.datetime.now()

    @noarg
    def LOCALDAY(self):
        """Displays the current day in numeric form."""
        return "%s" % self.now.day

    @noarg
    def LOCALDAY2(self):
        """[MW1.5+] Ditto with leading zero 01 .. 31)."""
        return "%02d" % self.now.day

    @noarg
    def LOCALDAYNAME(self):
        """Displays the current day in named form."""
        return self.now.strftime("%A")

    @noarg
    def LOCALDOW(self):
        """current day as number (0=Sunday, 1=Monday...)."""
        return str((self.now.weekday()+1) % 7)

    @noarg
    def LOCALMONTH(self):
        """The number 01 .. 12 of the current month."""
        return "%02d" % self.now.month

    @noarg
    def LOCALMONTHABBREV(self):
        """[MW1.5+] current month abbreviated Jan .. Dec."""
        return self.now.strftime("%b")

    @noarg        
    def LOCALMONTHNAME(self):
        """current month in named form January .. December.   """
        return self.now.strftime("%B")

    @noarg
    def LOCALTIME(self):
        """The current time of day (00:00 .. 23:59)."""
        return self.now.strftime("%H:%M")

    @noarg
    def LOCALWEEK(self):
        """Number of the current week (1-53) according to ISO 8601 with no leading zero."""
        return str(self.now.isocalendar()[1])

    @noarg
    def LOCALYEAR(self):
        """Returns the current year."""
        return str(self.now.year)

    @noarg
    def LOCALTIMESTAMP(self):
        """[MW1.7+] Returns the current time stamp. e.g.: 20060528125203"""
        return self.now.strftime("%Y%m%d%H%M%S")
    
from functools import wraps

class PageMagic(object):
    source={}
    def __init__(self, pagename='', server="http://en.wikipedia.org", revisionid=0):
        self.pagename = pagename
        self.server = server
        self.revisionid = revisionid
        
        self.niceurl = urlparse.urljoin(self.server, 'wiki')

    def _wrap_pagename(f):
        @wraps(f)
        def wrapper(self, args):
            pagename = self.pagename
            if args.args:
                pagename = args[0]
            return f(self, pagename)
        return wrapper

    def _quoted(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            return urlquote(f(*args, **kwargs).replace(' ', '_'))
        return wrapper
        
    @_wrap_pagename
    def PAGENAME(self, pagename):
        """Returns the name of the current page, including all levels (Title/Subtitle/Sub-subtitle)"""
        return self.nshandler.splitname(pagename)[1]
    
    """same as PAGENAME but More URL-friendly percent encoded
    special characters (To use an articlename in an external link).
    """
    PAGENAMEE = _quoted(PAGENAME)

    @_wrap_pagename
    def FULLPAGENAME(self, pagename):
        return pagename

    FULLPAGENAMEE = _quoted(FULLPAGENAME)
    
    @_wrap_pagename
    def SUBPAGENAME(self, pagename):
        """[MW1.6+] Returns the name of the current page, excluding parent
        pages ('Title/Subtitle' becomes 'Subtitle').
        """        
        return pagename.split('/')[-1]

    SUBPAGENAMEE = _quoted(SUBPAGENAME)

    @_wrap_pagename
    def BASEPAGENAME(self, pagename):
        """[MW1.7+] The basename of a subpage ('Title/Subtitle' becomes 'Title')
        """
        return self.nshandler.splitname(pagename)[1].rsplit('/', 1)[0]

    BASEPAGENAMEE = _quoted(BASEPAGENAME)

    @_wrap_pagename
    def NAMESPACE(self, pagename):
        """Returns the name of the namespace the current page resides in."""
        ns, partial, full = self.nshandler.splitname(pagename)
        return full[:-len(partial)-1]

    NAMESPACEE = _quoted(NAMESPACE)

    @_wrap_pagename
    def TALKSPACE(self, pagename):
        ns, partial, fullname = self.nshandler.splitname(pagename)
        if not ns % 2:
            ns += 1
        return self.nshandler.get_nsname_by_number(ns)

    TALKSPACEE = _quoted(TALKSPACE)

    @_wrap_pagename
    def SUBJECTSPACE(self, pagename):
        ns, partial, fullname = self.nshandler.splitname(pagename)
        if ns % 2:
            ns -= 1
        return self.nshandler.get_nsname_by_number(ns)

    SUBJECTSPACEE = _quoted(SUBJECTSPACE)
    ARTICLESPACE = SUBJECTSPACE
    ARTICLESPACEE = SUBJECTSPACEE

    @_wrap_pagename
    def TALKPAGENAME(self, pagename):
        ns, partial, fullname = self.nshandler.splitname(pagename)
        if not ns % 2:
            ns += 1
        return self.nshandler.get_nsname_by_number(ns) + ':' + partial

    TALKPAGENAMEE = _quoted(TALKPAGENAME)

    @_wrap_pagename
    def SUBJECTPAGENAME(self, pagename):
        ns, partial, fullname = self.nshandler.splitname(pagename)
        if ns % 2:
            ns -= 1
        return self.nshandler.get_nsname_by_number(ns) + ':' + partial

    SUBJECTPAGENAMEE = _quoted(SUBJECTPAGENAME)
    ARTICLEPAGENAME = SUBJECTPAGENAME
    ARTICLEPAGENAMEE = SUBJECTPAGENAMEE

    def REVISIONID(self, args):
        """[MW1.5+] The unique identifying number of a page, see Help:Diff."""
        return str(self.revisionid)

    @noarg
    def SITENAME(self):
        """Value of $wgSitename."""
        return ""

    def NS(self, args):
        """Returns the name of a given namespace number."""
        try:
            namespaces = self.siteinfo["namespaces"]
        except (AttributeError, KeyError):
            from mwlib import siteinfo
            namespaces = siteinfo.get_siteinfo("en")["namespaces"]

        ns = args[0]
        try:
            retval = namespaces[ns]['*']
        except KeyError:
            retval = ''

        return retval 
    
    def LOCALURL(self, args):
        """Returns the local URL of a given page. The page might not exist."""
        url = "/wiki/"+ "".join(args.get(0, u""))
        return url 

    def LOCALURLE(self, args):
        """Returns the local URL of a given page. The page might not exist."""        
        return urlquote(self.LOCALURL(args))
    
    def URLENCODE(self, args):
        """[MW1.7+] To use a variable (parameter in a template) with spaces in an external link."""
        url = urllib.quote_plus(args[0].encode('utf-8'))
        return url

    @noarg
    def SERVER(self):
        """Value of $wgServer"""
        return self.server

    def FULLURL(self, args):
        a=args[0].capitalize().replace(' ', '_')
        a=urllib.quote_plus(a.encode('utf-8'))
        if len(args)>=2:
            q = "?%s" % args[1]
        else:
            q = ""
        return '%s/%s%s' % (self.niceurl, a, q)
    
    @noarg        
    def SERVERNAME(self):
        return self.server[len('http://'):]


class NumberMagic(object):
    def NUMBEROFARTICLES(self, args):
        """A variable which returns the total number of articles on the Wiki."""
        return "0"
    
    def NUMBEROFPAGES(self, args):
        """[MW1.7+] Returns the total number of pages. """
        return "0"

    def NUMBEROFFILES(self, args):
        """[MW1.5+] Returns the number of uploaded files (rows in the image table)."""
        return "0"

    def NUMBEROFUSERS(self, args):
        """[MW1.7+] Returns the number of registered users (rows in the user table)."""
        return "0"

    def CURRENTVERSION(self, args):
        """[MW1.7+] Returns the current version of MediaWiki being run. [5]"""
        return "1.7alpha"



class StringMagic(object):
    @singlearg
    def LC(self, a):
        return a.lower()

    @singlearg
    def UC(self, a):
        return a.upper()

    @singlearg
    def LCFIRST(self, a):
        return a[:1].lower()+a[1:]

    @singlearg
    def UCFIRST(self, a):
        return a[:1].upper()+a[1:]

    @singlearg
    def FORMATNUM(self, a):
        return a

    def PADLEFT(self, args):
        s=args[0]
        try:
            width=int(args[1])
        except ValueError:
            return s

        fillstr = args[2] or u'0'
        return ''.join([fillstr[i % len(fillstr)] for i in range(width - len(s))]) + s

    def PADRIGHT(self, args):
        s=args[0]
        try:
            width=int(args[1])
        except ValueError:
            return s

        fillstr = args[2] or u'0'
        return s + ''.join([fillstr[i % len(fillstr)] for i in range(width - len(s))])

    
class ParserFunctions(object):
    wikidb = None
    def _error(self,s):
        return '<strong class="error">%s</strong>' % (s,)

    def LANGUAGE(self, args):
        """implement http://meta.wikimedia.org/wiki/Help:Parser_function#.23language:"""
        
        return args[0] # FIXME this is just a dummy implementation.
    
    def TAG(self, args):
        name = args[0].strip()
        r= u"<%s>%s</%s>" % (name, args[1], name)
        return r

    def IFEXIST(self, args):
        name = args[0]
        if not name or not self.wikidb:
            return args.get(args[2], "")

        nsnum, suffix, full = self.wikidb.nshandler.splitname(name)
        if nsnum==-2:
            exists = bool(self.wikidb.normalize_and_get_image_path(name.split(":")[1]))
        else:
            exists = bool(self.wikidb.normalize_and_get_page(name, 0))

        if exists:
            return args[1]
        else:
            return args[2]

    def EXPR(self, rl):
        import math
        if rl:
            try:
                ex = rl[0].strip()
                if not ex:
                    return u""
                val = expr.expr(ex)
                if int(val)==val and math.fabs(val)<1e14:
                    return str(int(val))
                r=str(float(val))
            except Exception, err:                
                # log("ERROR: error while evaluating #expr:%r\n" % (ex,))
                return self._error(err)

            if "e" in r:
                f,i = r.split("e")
                i=int(i)
                if i<0:
                    sign = ''
                else:
                    sign = '+'
                fixed=str(float(f))+"E"+sign+str(int(i))
                return fixed
            return r
        return u"0"
    

    def IFEXPR(self, rl):
        try:
            ex = rl[0].strip()
            if ex:
                r = expr.expr(rl[0])
            else:
                r = False
        except Exception, err:
            # log("ERROR: error while evaluating #ifexpr:%r\n" % (rl[0],))
            return self._error(err)

        if r:
            return rl[1]
        else:
            return rl[2]

    
    def TITLEPARTS(self, args):
        title = args[0]
        try:
            numseg = int(args[1])
        except ValueError:
            numseg = 0
            
        try:
            start = int(args[2])
        except ValueError:
            start = 1
        
        if start>0:    
            start -= 1
            
        parts = title.split("/")[start:]
        if numseg:
            parts = parts[:numseg]
        return "/".join(parts)

    def IFERROR(self, args):
        val = args[0]
        bad=args[1]
        good = args.get(2, None)
        if good is None:
            good = val
            
        if iferror_rx.search(val):
            return bad
        else:
            return good
        
        
for x in dir(ParserFunctions):
    if x.startswith("_"):
        continue    
    setattr(ParserFunctions, "#"+x, getattr(ParserFunctions, x))
    delattr(ParserFunctions, x)

class DummyResolver(object):
    pass

class MagicResolver(TimeMagic, LocaltimeMagic, PageMagic, NumberMagic, StringMagic, ParserFunctions, OtherMagic, DummyResolver):
    local_values = None
    def __call__(self, name, args):
        try:
            name = str(name)
        except UnicodeEncodeError:
            return None

        upper = name.upper()
        
        if self.local_values:
            try:
                return self.local_values[upper]
            except KeyError:
                pass
        
        m = getattr(self, upper, None)
        if m is None:
            return None
        
        if isinstance(m, basestring):
            return m

        res = m(args) or ''  # FIXME: catch TypeErros
        assert isinstance(res, basestring), "MAGIC %r returned %r" % (name, res)
        return res

    def has_magic(self, name):
        try:
            name = str(name)
        except UnicodeEncodeError:
            return False
        
        
        m = getattr(self, name.upper(), None)
        return m is not None



magic_words = ['basepagename', 'basepagenamee', 'contentlanguage', 'currentday', 'currentday2', 'currentdayname', 'currentdow', 'currenthour', 'currentmonth', 'currentmonthabbrev', 'currentmonthname', 'currentmonthnamegen', 'currenttime', 'currenttimestamp', 'currentversion', 'currentweek', 'currentyear', 'defaultsort', 'directionmark', 'displaytitle', 'fullpagename', 'fullpagenamee', 'language', 'localday', 'localday2', 'localdayname', 'localdow', 'localhour', 'localmonth', 'localmonthabbrev', 'localmonthname', 'localmonthnamegen', 'localtime', 'localtimestamp', 'localweek', 'localyear', 'namespace', 'namespacee', 'newsectionlink', 'numberofadmins', 'numberofarticles', 'numberofedits', 'numberoffiles', 'numberofpages', 'numberofusers', 'pagename', 'pagenamee', 'pagesinnamespace', 'revisionday', 'revisionday2', 'revisionid', 'revisionmonth', 'revisiontimestamp', 'revisionyear', 'scriptpath', 'server', 'servername', 'sitename', 'subjectpagename', 'subjectpagenamee', 'subjectspace', 'subjectspacee', 'subpagename', 'subpagenamee', 'talkpagename', 'talkpagenamee', 'talkspace', 'talkspacee', 'urlencode']

def _populate_dummy():
    m=MagicResolver()

    def get_dummy(name):
        def resolve(*args):
            log.warn("using dummy resolver for %s" % (name,))
            return u""
        return resolve

    missing = set()
    for x in magic_words:
        if not m.has_magic(x):
            missing.add(x)
            setattr(DummyResolver, x.upper(), get_dummy(x))

    if missing:
        missing = list(missing)
        missing.sort()
        #log.info("installed dummy resolvers for %s" % (", ".join(missing),))

_populate_dummy()
