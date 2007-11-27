#! /usr/bin/env python

# Copyright (c) 2007, PediaPress GmbH
# See README.txt for additional licensing information.

"""expand magic variables/colon functions
http://meta.wikimedia.org/wiki/Help:Colon_function
http://meta.wikimedia.org/wiki/Help:Magic_words
http://meta.wikimedia.org/wiki/ParserFunctions
"""

import re
import datetime
import urllib

from mwlib.log import Log
log = Log("expander")

def singlearg(fun):
    def wrap(self, args):
        a=args.get("1", "")
        return fun(self, a)
    return wrap

def noarg(fun):
    def wrap(self, *args):
        return fun(self)
    return wrap


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
        url = "".join(args)
        return "/wiki"+url

    def LOCALURLE(self, args):
        """Returns the local URL of a given page. The page might not exist."""        
        return urllib.quote(self.LOCALURL(args))
    
    def URLENCODE(self, args):
        """[MW1.7+] To use a variable (parameter in a template) with spaces in an external link."""
        return urllib.quote_plus("".join(args))

    @noarg
    def SERVER(self):
        """Value of $wgServer"""
        return self.server

    def FULLURL(self, args):
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

class ParserFunctions(object):
    wikidb = None

    def IF(self, args):
        if args.get("1", ""):
            return args.get("2", "")
        else:
            return args.get("3", "")

    def IFEXIST(self, args):
        name = args.get("1", "")
        if not self.wikidb:
            return args.get("3", "")
        
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
            return args.get("2", "")
        else:
            return args.get("3", "")


            
    def IFEQ(self, args):
        pass

    def EXPR(self, args):
        e = args.get("1", "0")
        rx = re.compile("^[-+/*. ()0-9]*$")
        if rx.match(e):
            try:
                retval = str(eval(e))
            except:
                retval = "0"
        else:
            retval = "0"
            
        return retval
    

    def IFEXPR(self, args):
        return ""

    def SWITCH(self, args):
        v  = args.get("1", "")
        res = args.get(v, args.get("#default", ""))
        return res
    
for x in dir(ParserFunctions):
    if x.startswith("_"):
        continue    
    setattr(ParserFunctions, "#"+x, getattr(ParserFunctions, x))

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
            return ""
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
