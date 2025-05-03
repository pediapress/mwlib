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
import logging
import re
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar, Union
from urllib.parse import quote, quote_plus, urljoin, urlparse

from mwlib.parser import expr

if_error_rx = re.compile(r'<(div|span|p|strong)\s[^<>]*class="error"[^<>]*>', re.I)

log = logging.getLogger(__name__)


def single_arg(fun):
    @wraps(fun)
    def wrap(self, args: list) -> Any:
        arg = args[0] if args else ""
        return fun(self, arg)

    return wrap


def no_arg(fun):
    @wraps(fun)
    def wrap(self, *args) -> Any:
        return fun(self)

    return wrap


def as_numeric(str_number: str) -> int | float:
    try:
        return int(str_number)
    except ValueError:
        return float(str_number)


def maybe_numeric_compare(value1: str, value2: str) -> bool:
    if value1 == value2:
        return True
    try:
        value1 = as_numeric(value1)
        value2 = as_numeric(value2)
    except ValueError:
        return False

    return value1 == value2


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

    def __init__(self, pagename="", server="https://en.wikipedia.org", revisionid=0):
        self.pagename = pagename
        self.server = server
        self.the_revisionid = revisionid

        self.niceurl = urljoin(self.server, "wiki")

    def _wrap_pagename(foo: T) -> T:
        @wraps(foo)
        def wrapper(self: Any, args: list[Any]) -> Any:
            pagename = self.pagename
            if args:
                pagename = args[0]
            return foo(self, pagename)

        return wrapper

    def _quoted(foo):
        @wraps(foo)
        def wrapper(*args, **kwargs):
            return urlquote(foo(*args, **kwargs).replace(" ", "_"))

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
            from mwlib.network import siteinfo

            namespaces = siteinfo.get_siteinfo("en")["namespaces"]

        namespace = args[0]
        try:
            retval = namespaces[namespace]["*"]
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
        arg = args[0].capitalize().replace(" ", "_")
        arg = quote_plus(arg.encode("utf-8"))
        query = "?%s" % args[1] if len(args) >= 2 else ""
        return f"{self.niceurl}/{arg}{query}"

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
    def LC(self, input_string):
        return input_string.lower()

    @single_arg
    def UC(self, input_string):
        return input_string.upper()

    @single_arg
    def LCFIRST(self, input_string):
        return input_string[:1].lower() + input_string[1:]

    @single_arg
    def UCFIRST(self, input_string):
        return input_string[:1].upper() + input_string[1:]

    def PADLEFT(self, args):
        original_string = args[0]
        try:
            width = int(args[1])
        except ValueError:
            return original_string

        fill_str = args[2] or "0"
        return (
            "".join(
                [
                    fill_str[i % len(fill_str)]
                    for i in range(width - len(original_string))
                ]
            )
            + original_string
        )

    def PADRIGHT(self, args):
        original_string = args[0]
        try:
            width = int(args[1])
        except ValueError:
            return original_string

        fillstr = args[2] or "0"
        return original_string + "".join(
            [fillstr[i % len(fillstr)] for i in range(width - len(original_string))]
        )


class ParserFunctions:
    wikidb = None

    def _error(self, message):
        return f'<strong class="error">{message}</strong>'

    def LANGUAGE(self, args):
        """implement http://meta.wikimedia.org/wiki/Help:Parser_function#.23language:"""

        return args[0]  # FIXME this is just a dummy implementation.

    def TAG(self, args):
        name = args[0].strip()
        text_to_wrap = f"<{name}>{args[1]}</{name}>"
        return text_to_wrap

    def IFEXIST(self, args):
        name = args[0]
        if not name or not self.wikidb:
            return args.get(args[2], "")

        nsnum, _, _ = self.wikidb.nshandler.splitname(name)
        if nsnum == -2:
            exists = bool(self.wikidb.normalize_and_get_image_path(name.split(":")[1]))
        else:
            exists = bool(self.wikidb.normalize_and_get_page(name, 0))

        if exists:
            return args[1]
        else:
            return args[2]

    def EXPR(self, expression_list):
        import math

        if expression_list:
            try:
                expression = expression_list[0].strip()
                if not expression:
                    return ""
                val = expr.expr(expression)
                if int(val) == val and math.fabs(val) < 1e14:
                    return str(int(val))
                float_result = str(float(val))
            except Exception as err:
                return self._error(err)

            if "e" in float_result:
                mantissa, i = float_result.split("e")
                i = int(i)
                sign = "" if i < 0 else "+"
                fixed = str(float(mantissa)) + "E" + sign + str(int(i))
                return fixed
            return float_result
        return "0"

    def IFEXPR(self, expression_list):
        try:
            expression = expression_list[0].strip()
            evaluation_result = expr.expr(expression_list[0]) if expression else False
        except Exception as err:
            return self._error(err)

        if evaluation_result:
            return expression_list[1]
        else:
            return expression_list[2]

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


for foo_name in dir(ParserFunctions):
    if foo_name.startswith("_"):
        continue
    setattr(ParserFunctions, "#" + foo_name, getattr(ParserFunctions, foo_name))
    delattr(ParserFunctions, foo_name)


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

        method_to_invoke = getattr(self, upper, None)
        if method_to_invoke is None:
            return None

        if isinstance(method_to_invoke, str):
            return method_to_invoke

        res = method_to_invoke(args) or ""  # FIXME: catch TypeErros
        if not isinstance(res, str):
            raise TypeError(f"MAGIC {name!r} returned {res!r}")
        return res

    def has_magic(self, name):
        try:
            name = str(name)
        except UnicodeEncodeError:
            return False

        method = getattr(self, name.upper(), None)
        return method is not None


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
    magic_resolver = MagicResolver()

    def get_dummy(name):
        def resolve():
            log.warn(f"using dummy resolver for {name}")
            return ""

        return resolve

    missing = set()
    for word in magic_words:
        if not magic_resolver.has_magic(word):
            missing.add(word)
            setattr(DummyResolver, word.upper(), get_dummy(word))

    if missing:
        missing = list(missing)
        missing.sort()
        # log.info("installed dummy resolvers for %s" % (", ".join(missing),))


_populate_dummy()
