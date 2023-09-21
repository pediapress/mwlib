#! /usr/bin/env python
# pylint: disable=snake-case-naming-style


# Copyright (c) 2007-2009 PediaPress GmbH
# See README.md for additional licensing information.

"""expand magic variables/colon functions
https://meta.wikimedia.org/wiki/Help:Colon_function
https://meta.wikimedia.org/wiki/Help:Magic_words
https://meta.wikimedia.org/wiki/ParserFunctions
"""

import datetime
import re
from functools import wraps
from typing import Any, Callable, TypeVar, Union
from urllib.parse import quote, quote_plus, urljoin, urlparse

from mwlib import expr
from mwlib.log import Log

if_error_rx = re.compile(r'<(div|span|p|strong)\s[^<>]*class="error"[^<>]*>',
                         re.I)

log = Log("expander")


def single_arg(fun):
    @wraps(fun)
    def wrap(self, args: list) -> Any:
        a = args[0] if args else ""
        return fun(self, a)

    return wrap


def no_arg(fun):
    @wraps(fun)
    def wrap(self, *args) -> Any:
        return fun(self)

    return wrap


def as_numeric(x: str) -> Union[int, float]:
    try:
        return int(x)
    except ValueError:
        return float(x)


def maybe_numeric_compare(a: str, b: str) -> bool:
    if a == b:
        return True
    try:
        a = as_numeric(a)
        b = as_numeric(b)
    except ValueError:
        return False

    return a == b


def urlquote(url: str) -> str:
    if isinstance(url, str):
        url = url.encode("utf-8")
    return quote(url)


class OtherMagic:
    def DEFAULTSORT(self) -> str:
        """see https://en.wikipedia.org/wiki/Template:DEFAULTSORT"""
        return ""


class TimeMagic:
    utcnow = datetime.datetime.utcnow()

    @no_arg
    def CURRENTDAY(self) -> str:
        """Displays the current day in numeric form."""
        return f"{self.utcnow.day}"

    @no_arg
    def CURRENTDAY2(self) -> str:
        """[MW1.5+] Ditto with leading zero 01 .. 31)."""
        return f"{self.utcnow.day:02d}"

    @no_arg
    def CURRENTDAYNAME(self) -> str:
        """Displays the current day in named form."""
        return self.utcnow.strftime("%A")

    @no_arg
    def CURRENTDOW(self) -> str:
        """current day as number (0=Sunday, 1=Monday...)."""
        return str((self.utcnow.weekday() + 1) % 7)

    @no_arg
    def CURRENTMONTH(self) -> str:
        """The number 01 .. 12 of the current month."""
        return f"{self.utcnow.month:02d}"

    @no_arg
    def CURRENTMONTHABBREV(self) -> str:
        """[MW1.5+] current month abbreviated Jan .. Dec."""
        return self.utcnow.strftime("%b")

    @no_arg
    def CURRENTMONTHNAME(self) -> str:
        """current month in named form January .. December."""
        return self.utcnow.strftime("%B")

    @no_arg
    def CURRENTTIME(self) -> str:
        """The current time of day (00:00 .. 23:59)."""
        return self.utcnow.strftime("%H:%M")

    @no_arg
    def CURRENTWEEK(self) -> str:
        """Number of the current week (1-53) according
        to ISO 8601 with no leading zero."""
        return str(self.utcnow.isocalendar()[1])

    @no_arg
    def CURRENTYEAR(self) -> str:
        """Returns the current year."""
        return str(self.utcnow.year)

    @no_arg
    def CURRENTTIMESTAMP(self) -> str:
        """[MW1.7+] Returns the current time stamp. e.g.: 20060528125203"""
        return self.utcnow.strftime("%Y%m%d%H%M%S")


class LocaltimeMagic:
    now = datetime.datetime.now()

    @no_arg
    def LOCALDAY(self) -> str:
        """Displays the current day in numeric form."""
        return f"{self.now.day}"

    @no_arg
    def LOCALDAY2(self) -> str:
        """[MW1.5+] Ditto with leading zero 01 .. 31)."""
        return f"{self.now.day:02d}"

    @no_arg
    def LOCALDAYNAME(self) -> str:
        """Displays the current day in named form."""
        return self.now.strftime("%A")

    @no_arg
    def LOCALDOW(self) -> str:
        """current day as number (0=Sunday, 1=Monday...)."""
        return str((self.now.weekday() + 1) % 7)

    @no_arg
    def LOCALMONTH(self) -> str:
        """The number 01 .. 12 of the current month."""
        return f"{self.now.month:02d}"

    @no_arg
    def LOCALMONTHABBREV(self) -> str:
        """[MW1.5+] current month abbreviated Jan .. Dec."""
        return self.now.strftime("%b")

    @no_arg
    def LOCALMONTHNAME(self) -> str:
        """current month in named form January .. December."""
        return self.now.strftime("%B")

    @no_arg
    def LOCALTIME(self) -> str:
        """The current time of day (00:00 .. 23:59)."""
        return self.now.strftime("%H:%M")

    @no_arg
    def LOCALWEEK(self) -> str:
        """Number of the current week (1-53) according
        to ISO 8601 with no leading zero."""
        return str(self.now.isocalendar()[1])

    @no_arg
    def LOCALYEAR(self) -> str:
        """Returns the current year."""
        return str(self.now.year)

    @no_arg
    def LOCALTIMESTAMP(self) -> str:
        """[MW1.7+] Returns the current time stamp. e.g.: 20060528125203"""
        return self.now.strftime("%Y%m%d%H%M%S")


T = TypeVar("T", bound=Callable[..., Any])


class PageMagic:
    source = {}
    nshandler = None

    def __init__(self, pagename="",
                 server="https://en.wikipedia.org", revisionid=0):
        self.pagename = pagename
        self.server = server
        self.the_revisionid = revisionid

        self.niceurl = urljoin(self.server, "wiki")

    def _wrap_pagename(f: T) -> T:
        @wraps(f)
        def wrapper(self: Any, args: list[Any]) -> Any:
            pagename = self.pagename
            if args:
                pagename = args[0]
            return f(self, pagename)

        return wrapper

    def _quoted(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            return urlquote(f(*args, **kwargs).replace(" ", "_"))

        return wrapper

    @_wrap_pagename
    def PAGENAME(self, pagename):
        """Returns the name of the current page, including all levels
        (Title/Subtitle/Sub-subtitle)"""
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
        return pagename.split("/")[-1]

    SUBPAGENAMEE = _quoted(SUBPAGENAME)

    @_wrap_pagename
    def BASEPAGENAME(self, pagename):
        """[MW1.7+] The basename of a subpage
        ('Title/Subtitle' becomes 'Title')"""
        return self.nshandler.splitname(pagename)[1].rsplit("/", 1)[0]

    BASEPAGENAMEE = _quoted(BASEPAGENAME)

    @_wrap_pagename
    def NAMESPACE(self, pagename):
        """Returns the name of the namespace the current page resides in."""
        _, partial, full = self.nshandler.splitname(pagename)
        return full[: -len(partial) - 1]

    NAMESPACEE = _quoted(NAMESPACE)

    @_wrap_pagename
    def TALKSPACE(self, pagename):
        namespace, _, _ = self.nshandler.splitname(pagename)
        if not namespace % 2:
            namespace += 1
        return self.nshandler.get_nsname_by_number(namespace)

    TALKSPACEE = _quoted(TALKSPACE)

    @_wrap_pagename
    def SUBJECTSPACE(self, pagename):
        namespace, _, _ = self.nshandler.splitname(pagename)
        if namespace % 2:
            namespace -= 1
        return self.nshandler.get_nsname_by_number(namespace)

    SUBJECTSPACEE = _quoted(SUBJECTSPACE)
    ARTICLESPACE = SUBJECTSPACE
    ARTICLESPACEE = SUBJECTSPACEE

    @_wrap_pagename
    def TALKPAGENAME(self, pagename):
        namespace, partial, _ = self.nshandler.splitname(pagename)
        if not namespace % 2:
            namespace += 1
        return self.nshandler.get_nsname_by_number(namespace) + ":" + partial

    TALKPAGENAMEE = _quoted(TALKPAGENAME)

    @_wrap_pagename
    def SUBJECTPAGENAME(self, pagename):
        namespace, partial, _ = self.nshandler.splitname(pagename)
        if namespace % 2:
            namespace -= 1
        return self.nshandler.get_nsname_by_number(namespace) + ":" + partial

    SUBJECTPAGENAMEE = _quoted(SUBJECTPAGENAME)
    ARTICLEPAGENAME = SUBJECTPAGENAME
    ARTICLEPAGENAMEE = SUBJECTPAGENAMEE

    def REVISIONID(self):
        """[MW1.5+] The unique identifying number of a page, see Help:Diff."""
        return str(self.the_revisionid)

    @no_arg
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
            retval = namespaces[ns]["*"]
        except KeyError:
            retval = ""

        return retval

    def LOCALURL(self, args):
        """Returns the local URL of a given page. The page might not exist."""
        url = "/wiki/" + "".join(args.get(0, ""))
        return url

    def LOCALURLE(self, args):
        """Returns the local URL of a given page. The page might not exist."""
        return urlquote(self.LOCALURL(args))

    def URLENCODE(self, args):
        """[MW1.7+] To use a variable (parameter in a template)
        with spaces in an external link."""
        url = quote_plus(args[0].encode("utf-8"))
        return url

    @no_arg
    def SERVER(self):
        """Value of $wgServer"""
        return self.server

    def FULLURL(self, args):
        a = args[0].capitalize().replace(" ", "_")
        a = quote_plus(a.encode("utf-8"))
        q = "?%s" % args[1] if len(args) >= 2 else ""
        return f"{self.niceurl}/{a}{q}"

    @no_arg
    def SERVERNAME(self):
        parsed_url = urlparse(self.server)
        return parsed_url.netloc


class NumberMagic:
    def NUMBEROFARTICLES(self):
        """A variable which returns the total
        number of articles on the Wiki."""
        return "0"

    def NUMBEROFPAGES(self):
        """[MW1.7+] Returns the total number of pages."""
        return "0"

    def NUMBEROFFILES(self):
        """[MW1.5+] Returns the number of uploaded
        files (rows in the image table)."""
        return "0"

    def NUMBEROFUSERS(self):
        """[MW1.7+] Returns the number of registered
        users (rows in the user table)."""
        return "0"

    def CURRENTVERSION(self):
        """[MW1.7+] Returns the current version of MediaWiki being run. [5]"""
        return "1.7alpha"


class StringMagic:
    @single_arg
    def LC(self, a):
        return a.lower()

    @single_arg
    def UC(self, a):
        return a.upper()

    @single_arg
    def LCFIRST(self, a):
        return a[:1].lower() + a[1:]

    @single_arg
    def UCFIRST(self, a):
        return a[:1].upper() + a[1:]

    def PADLEFT(self, args):
        s = args[0]
        try:
            width = int(args[1])
        except ValueError:
            return s

        fill_str = args[2] or "0"
        return "".join([fill_str[i % len(fill_str)] for i in range(width - len(s))]) + s

    def PADRIGHT(self, args):
        s = args[0]
        try:
            width = int(args[1])
        except ValueError:
            return s

        fillstr = args[2] or "0"
        return s + "".join([fillstr[i % len(fillstr)] for i in range(width - len(s))])


class ParserFunctions:
    wikidb = None

    def _error(self, s):
        return f'<strong class="error">{s}</strong>'

    def LANGUAGE(self, args):
        """implement http://meta.wikimedia.org/wiki/Help:Parser_function#.23language:"""

        return args[0]  # FIXME this is just a dummy implementation.

    def TAG(self, args):
        name = args[0].strip()
        r = f"<{name}>{args[1]}</{name}>"
        return r

    def IFEXIST(self, args):
        name = args[0]
        if not name or not self.wikidb:
            return args.get(args[2], "")

        nsnum, suffix, full = self.wikidb.nshandler.splitname(name)
        if nsnum == -2:
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
                    return ""
                val = expr.expr(ex)
                if int(val) == val and math.fabs(val) < 1e14:
                    return str(int(val))
                r = str(float(val))
            except Exception as err:
                # log("ERROR: error while evaluating #expr:%r\n" % (ex,))
                return self._error(err)

            if "e" in r:
                f, i = r.split("e")
                i = int(i)
                sign = "" if i < 0 else "+"
                fixed = str(float(f)) + "E" + sign + str(int(i))
                return fixed
            return r
        return "0"

    def IFEXPR(self, rl):
        try:
            ex = rl[0].strip()
            r = expr.expr(rl[0]) if ex else False
        except Exception as err:
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

        if start > 0:
            start -= 1

        parts = title.split("/")[start:]
        if numseg:
            parts = parts[:numseg]
        return "/".join(parts)

    def IFERROR(self, args):
        val = args[0]
        bad = args[1]
        good = args.get(2, None)
        if good is None:
            good = val

        if if_error_rx.search(val):
            return bad
        else:
            return good


for x in dir(ParserFunctions):
    if x.startswith("_"):
        continue
    setattr(ParserFunctions, "#" + x, getattr(ParserFunctions, x))
    delattr(ParserFunctions, x)


class DummyResolver:
    pass


class MagicResolver(
    TimeMagic,
    LocaltimeMagic,
    PageMagic,
    NumberMagic,
    StringMagic,
    ParserFunctions,
    OtherMagic,
    DummyResolver,
):
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

        if isinstance(m, str):
            return m

        res = m(args) or ""  # FIXME: catch TypeErros
        if not isinstance(res, str):
            raise TypeError(f"MAGIC {name!r} returned {res!r}")
        return res

    def has_magic(self, name):
        try:
            name = str(name)
        except UnicodeEncodeError:
            return False

        m = getattr(self, name.upper(), None)
        return m is not None


magic_words = [
    "basepagename",
    "basepagenamee",
    "contentlanguage",
    "currentday",
    "currentday2",
    "currentdayname",
    "currentdow",
    "currenthour",
    "currentmonth",
    "currentmonthabbrev",
    "currentmonthname",
    "currentmonthnamegen",
    "currenttime",
    "currenttimestamp",
    "currentversion",
    "currentweek",
    "currentyear",
    "defaultsort",
    "directionmark",
    "displaytitle",
    "fullpagename",
    "fullpagenamee",
    "language",
    "localday",
    "localday2",
    "localdayname",
    "localdow",
    "localhour",
    "localmonth",
    "localmonthabbrev",
    "localmonthname",
    "localmonthnamegen",
    "localtime",
    "localtimestamp",
    "localweek",
    "localyear",
    "namespace",
    "namespacee",
    "newsectionlink",
    "numberofadmins",
    "numberofarticles",
    "numberofedits",
    "numberoffiles",
    "numberofpages",
    "numberofusers",
    "pagename",
    "pagenamee",
    "pagesinnamespace",
    "revisionday",
    "revisionday2",
    "revisionid",
    "revisionmonth",
    "revisiontimestamp",
    "revisionyear",
    "scriptpath",
    "server",
    "servername",
    "sitename",
    "subjectpagename",
    "subjectpagenamee",
    "subjectspace",
    "subjectspacee",
    "subpagename",
    "subpagenamee",
    "talkpagename",
    "talkpagenamee",
    "talkspace",
    "talkspacee",
    "urlencode",
]


def _populate_dummy():
    m = MagicResolver()

    def get_dummy(name):
        def resolve():
            log.warn(f"using dummy resolver for {name}")
            return ""

        return resolve

    missing = set()
    for word in magic_words:
        if not m.has_magic(word):
            missing.add(word)
            setattr(DummyResolver, word.upper(), get_dummy(word))

    if missing:
        missing = list(missing)
        missing.sort()
        # log.info("installed dummy resolvers for %s" % (", ".join(missing),))


_populate_dummy()
