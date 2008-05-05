#! /usr/bin/env python

# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.

"""expand magic variables/colon functions
http://meta.wikimedia.org/wiki/Help:Colon_function
http://meta.wikimedia.org/wiki/Help:Magic_words
http://meta.wikimedia.org/wiki/ParserFunctions
"""

import datetime
import urllib
from mwlib.log import Log
from mwlib import expr

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
        a=as_numeric(a)
        b=as_numeric(b)
    except ValueError:
        return False

    return a==b


class OtherMagic(object):
    def DEFAULTSORT(self, args):
        """see http://en.wikipedia.org/wiki/Template:DEFAULTSORT"""
        return u""


class TimeMagic(object):
    now = datetime.datetime.now()

    @noarg
    def CURRENTDAY(self):
        """Displays the current day in numeric form."""
        return "%s" % self.now.day

    @noarg
    def CURRENTDAY2(self):
        """[MW1.5+] Ditto with leading zero 01 .. 31)."""
        return "%02d" % self.now.day

    @noarg
    def CURRENTDAYNAME(self):
        """Displays the current day in named form."""
        return self.now.strftime("%A")

    @noarg
    def CURRENTDOW(self):
        """current day as number (0=Sunday, 1=Monday...)."""
        return str((self.now.weekday()+1) % 7)

    @noarg
    def CURRENTMONTH(self):
        """The number 01 .. 12 of the current month."""
        return "%02d" % self.now.month

    @noarg
    def CURRENTMONTHABBREV(self):
        """[MW1.5+] current month abbreviated Jan .. Dec."""
        return self.now.strftime("%b")

    @noarg        
    def CURRENTMONTHNAME(self):
        """current month in named form January .. December.   """
        return self.now.strftime("%B")

    @noarg
    def CURRENTTIME(self):
        """The current time of day (00:00 .. 23:59)."""
        return self.now.strftime("%H:%M")

    @noarg
    def CURRENTWEEK(self):
        """Number of the current week (1-53) according to ISO 8601 with no leading zero."""
        return str(self.now.isocalendar()[1])

    @noarg
    def CURRENTYEAR(self):
        """Returns the current year."""
        return str(self.now.year)

    @noarg
    def CURRENTTIMESTAMP(self):
        """[MW1.7+] Returns the current time stamp. e.g.: 20060528125203"""
        return self.now.strftime("%Y%m%d%H%M%S")

    def MONTHNAME(self, args):
        rl = args
        if not rl:
            return u"Missing required parameter 1=month!"
        try:
            m=int(rl[0].strip()) % 12
        except ValueError:
            return u"month should be an integer"
        if m==0:
            m=12

        return datetime.datetime(2000, m, 1).strftime("%B")

class PageMagic(object):
    def __init__(self, pagename='', server="http://en.wikipedia.org", revisionid=0):
        self.pagename = pagename
        self.server = server
        self.revisionid = revisionid
        
    def PAGENAME(self, args):
        """Returns the name of the current page, including all levels (Title/Subtitle/Sub-subtitle)"""
        return self.pagename
    
    def PAGENAMEE(self, args):
        """same as PAGENAME but More URL-friendly percent encoded
        special characters (To use an articlename in an external link).
        """
        return urllib.quote(self.pagename.encode('utf8'))

    
    def SUBPAGENAME(self, args):
        """[MW1.6+] Returns the name of the current page, excluding parent
        pages ('Title/Subtitle' becomes 'Subtitle').
        """        
        return self.pagename.split('/')[-1]

    def SUBPAGENAMEE(self, args):
        return urllib.quote(self.SUBPAGENAMEE())

    def BASEPAGENAME(self, args):
        """[MW1.7+] The basename of a subpage ('Title/Subtitle' becomes 'Title')
        """
        return self.pagename.rsplit('/', 1)[0]

    def BASEPAGENAMEE(self, args):
        """[MW1.7+] The basename of a subpage ('Title/Subtitle' becomes 'Title')
        """
        return urllib.quote(self.BASEPAGENAME(args))

    def NAMESPACE(self, args):
        """Returns the name of the namespace the current page resides in."""
        return u""   # we currently only have articles living in the main/empty namespace

    def NAMESPACEE(self, args):
        """Returns the name of the namespace the current page resides in. (quoted)"""        
        return urllib.quote(self.NAMESPACE(args))

    def REVISIONID(self, args):
        """[MW1.5+] The unique identifying number of a page, see Help:Diff."""
        return str(self.revisionid)

    @noarg
    def SITENAME(self):
        """Value of $wgSitename."""
        return ""

    def NS(self, args):
        """Returns the name of a given namespace number."""
        return "++NS not implemented++"

    def LOCALURL(self, args):
        """Returns the local URL of a given page. The page might not exist."""
        try:
            url = "/wiki"+ "".join(args)
        except:
            url = '' # FIXME
        return "/wiki"+url

    def LOCALURLE(self, args):
        """Returns the local URL of a given page. The page might not exist."""        
        return urllib.quote(self.LOCALURL(args))
    
    def URLENCODE(self, args):
        """[MW1.7+] To use a variable (parameter in a template) with spaces in an external link."""
        try:
            url = urllib.quote_plus("".join(args[0]))
        except:
            url = "".join(args[0])
        return url

    @noarg
    def SERVER(self):
        """Value of $wgServer"""
        return self.server

    def FULLURL(self, args):
        return u''
        u = "".join(args)
        self.SERVERNAME({})

    @noarg        
    def SERVERNAME(self):
        return self.SERVER({})[len("http://"):]


class NumberMagic(object):
    def DISPLAYTITLE(self, args):
        """[MW 1.7+] (unclear)"""
        return ""

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

class ParserFunctions(object):
    wikidb = None
    def _error(self,s):
        return '<strong class="error">%s</strong>' % (s,)
    
    def TAG(self, args):
        name = args[0].strip()
        r= u"<%s>%s</%s>" % (name, args[1], name)
        return r
    

    def IF(self, rl):
        if rl[0]:
            return rl[1]
        else:
            return rl[2]

    def IFEXIST(self, args):
        name = args[0]
        if not self.wikidb:
            return args.get(args[2], "")
        
        # wrong place. FIXME.
        if ':' in name:
            ns, name = name.split(':', 1)
            if ns.lower() in ['vorlage', 'template']:
                r=self.wikidb.getTemplate(name)
            else:
                r=None
        else:
            r=self.wikidb.getRawArticle(name)

        if r:
            return args[1]
        else:
            return args[2]


            
    def IFEQ(self, rl):
        if maybe_numeric_compare(rl[0], rl[1]):
            return rl[2]
        else:
            return rl[3]

    def EXPR(self, rl):
        if rl:
            try:
                r=str(expr.expr(rl[0]))
            except Exception, err:
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
            r = expr.expr(rl[0])
        except Exception, err:
            return self._error(err)

        if r:
            return rl[1]
        else:
            return rl[2]

    def SWITCH(self, args):
        """see http://meta.wikimedia.org/wiki/ParserFunctions#.23switch:"""
        cmpval = args[0].strip()
        found=False # used for fall through 
        for c in args[1:]:
            if '=' in c:
                val, result = c.split('=', 1)
                val=val.strip()
                result=result.strip()
                if found or maybe_numeric_compare(val, cmpval):
                    return result
            else:
                if maybe_numeric_compare(cmpval,c.strip()):
                    found=True

        d=args["#default"]
        if d:
            return d

        
        last = args[-1]

        if '=' not in last:
            return last
        return u''
    
    def TITLEPARTS(self, args):
        title = args[0]
        try:
            numseg = int(args[1])
        except ValueError:
            numseq = 0
            
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
        errmark = '<strong class="error">'
        val = args[0]
        bad=args[1]
        good=args[2] or val
        
        if errmark in val:
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

class MagicResolver(TimeMagic, PageMagic, NumberMagic, StringMagic, ParserFunctions, OtherMagic, DummyResolver):
    def __call__(self, name, args):
        try:
            name = str(name)
        except UnicodeEncodeError:
            return None
        
        
        m = getattr(self, name.upper(), None)
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
