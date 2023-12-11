# Copyright (c) 2007-2009 PediaPress GmbH
# See README.md for additional licensing information.

from typing import Any

from mwlib import metabook, nshandling, siteinfo
from mwlib.templ import log, magics, mwlocals, parser
from mwlib.templ.marks import dummy_mark, eqmark, Mark, maybe_newline
from mwlib.miscellaneous.uniq import Uniquifier


class TemplateRecursion(Exception):
    pass


def flatten(node: Any, expander: Any, variables: Any, res: list[str]) -> bool:
    t = type(node)
    if isinstance(node, str):
        res.append(node)
        return True

    if expander.recursion_count > expander.recursion_limit:
        raise TemplateRecursion()

    expander.recursion_count += 1
    try:
        before = variables.count
        old_len = len(res)
        try:
            if t is list or t is tuple:  # noqa
                for x in node:
                    flatten(x, expander, variables, res)
            else:
                node.flatten(expander, variables, res)
        except TemplateRecursion:
            if expander.recursion_count > 2:
                raise
            del res[old_len:]
            log.warning("template recursion error ignored")
        after = variables.count
        return before == after
    finally:
        expander.recursion_count -= 1


class MemoryLimitError(Exception):
    pass


def equal_split(node):
    if isinstance(node, str):
        return None, node

    try:
        idx = node.index(eqmark)
    except ValueError:
        return None, node

    return node[:idx], node[idx + 1 :]


class ArgumentList:
    def __init__(self, args=(), expander=None, variables=None):
        self.args = tuple(args)

        assert expander is not None
        # assert variables is not None

        self.expander = expander
        self.variables = variables
        self.var_count = 1
        self.var_num = 0

        self.named_args = {}
        self.count = 0

    def __len__(self):
        self.count += 1
        return len(self.args)

    def __getitem__(self, n):
        self.count += 1
        if isinstance(n, slice):
            start = n.start or 0
            stop = n.stop or len(self)
            return [self.get(x, None) or "" for x in range(start, stop)]
        return self.get(n, None) or ""

    def get(self, n, default):
        self.count += 1
        if isinstance(n, int):
            try:
                a = self.args[n]
            except IndexError:
                return default
            if isinstance(a, str):
                return a.strip()
            tmp = []
            flatten(a, self.expander, self.variables, tmp)
            insert_implicit_newlines(tmp)
            tmp = "".join(tmp).strip()
            if len(tmp) > 256 * 1024:
                raise MemoryLimitError("template argument too long: %s bytes" % len(tmp))
            # FIXME: cache value ???
            return tmp

        assert isinstance(n, (str, int)), "expected int or string"

        if n not in self.named_args:
            while self.var_num < len(self.args):
                arg = self.args[self.var_num]
                self.var_num += 1

                name, val = equal_split(arg)
                if name is not None:
                    tmp = []
                    flatten(name, self.expander, self.variables, tmp)
                    insert_implicit_newlines(tmp)
                    name = "".join(tmp).strip()
                    do_strip = True
                else:
                    name = str(self.var_count)
                    self.var_count += 1
                    do_strip = False

                if do_strip and isinstance(val, str):
                    val = val.strip()
                self.named_args[name] = (do_strip, val)

                if n == name:
                    break

        try:
            do_strip, val = self.named_args[n]
            if isinstance(val, str):
                return val
        except KeyError:
            return default

        tmp = []
        flatten(val, self.expander, self.variables, tmp)
        insert_implicit_newlines(tmp)
        tmp = "".join(tmp)
        if do_strip:
            tmp = tmp.strip()

        self.named_args[n] = (do_strip, tmp)
        return tmp


def is_implicit_newline(raw):
    """should we add a newline to templates starting with *, #, :, ;, {|
    see: https://meta.wikimedia.org/wiki/Help:Newlines_and_spaces#Automatic_newline_at_the_start
    """
    sw = raw.startswith
    return any(sw(x) for x in ("*", "#", ":", ";", "{|"))


def insert_implicit_newlines(res, maybe_newline=maybe_newline):
    # do not pass the second argument
    res.append(dummy_mark)
    res.append(dummy_mark)

    for i, p in enumerate(res):
        if p is maybe_newline:
            s1 = res[i + 1]
            s2 = res[i + 2]
            if i and res[i - 1].endswith("\n"):
                continue

            if isinstance(s1, Mark):
                continue
            if len(s1) >= 2:
                if is_implicit_newline(s1):
                    res[i] = "\n"
            else:
                if is_implicit_newline("".join([s1, s2])):
                    res[i] = "\n"
    del res[-2:]


class Expander:
    magic_displaytitle = None  # set via {{DISPLAYTITLE:...}}

    def __init__(self, txt, pagename="", wikidb=None, recursion_limit=100):
        assert wikidb is not None, "must supply wikidb argument in Expander.__init__"
        self.pagename = pagename
        self.db = wikidb
        self.uniquifier = Uniquifier()

        si = None
        try:
            si = self.db.get_siteinfo()
        except Exception as err:
            print("Caught: %s" % err)

        if si is None:
            print(f"WARNING: failed to get siteinfo from {self.db!r}")
            si = siteinfo.get_siteinfo("de")

        self.nshandler = nshandler = nshandling.NsHandler(si)
        self.siteinfo = si

        if self.db and hasattr(self.db, "get_source"):
            source = self.db.get_source(pagename) or metabook.source()
            local_values = source.locals or ""
            local_values = mwlocals.parse_locals(local_values)
        else:
            local_values = None
            source = {}

        # XXX we really should call Expander with a nuwiki.page object.
        revision_id = 0
        if self.db and hasattr(self.db, "nuwiki") and pagename:
            page = self.db.nuwiki.get_page(self.pagename)
            if page is not None:
                revision_id = getattr(page, "revid", 0) or 0

        self.resolver = magics.MagicResolver(pagename=pagename, revisionid=revision_id)
        self.resolver.siteinfo = si
        self.resolver.nshandler = nshandler

        self.resolver.wikidb = wikidb
        self.resolver.local_values = local_values
        self.resolver.source = source

        self.recursion_limit = recursion_limit
        self.recursion_count = 0
        self.aliasmap = parser.AliasMap(self.siteinfo)

        self.parsed = parser.parse(
            txt, included=False, replace_tags=self.replace_tags, siteinfo=self.siteinfo
        )
        # show(self.parsed)
        self.parsedTemplateCache = {}

    def resolve_magic_alias(self, name):
        return self.aliasmap.resolve_magic_alias(name)

    def replace_tags(self, txt):
        return self.uniquifier.replace_tags(txt)

    def get_parsed_template(self, name):
        if not name or name.startswith("[[") or "|" in name:
            return None

        if name.startswith("/"):
            name = self.pagename + name
            ns = 0
        else:
            ns = 10

        try:
            return self.parsedTemplateCache[name]
        except KeyError:
            pass

        page = self.db.normalize_and_get_page(name, ns)
        raw = page.rawtext if page else None

        res = None if raw is None else self._parse_raw_template(name=name, raw=raw)

        self.parsedTemplateCache[name] = res
        return res

    def _parse_raw_template(self, name, raw):
        return parser.parse(raw, replace_tags=self.replace_tags)

    def _expand(self, parsed, keep_uniq=False):
        res = ["\n"]  # guard, against implicit newlines at the beginning
        flatten(parsed, self, ArgumentList(expander=self), res)
        insert_implicit_newlines(res)
        res[0] = ""
        res = "".join(res)
        if not keep_uniq:
            res = self.uniquifier.replace_uniq(res)
        return res

    def parseAndExpand(self, txt, keep_uniq=False):
        parsed = parser.parse(txt, included=False, replace_tags=self.replace_tags)
        return self._expand(parsed, keep_uniq=keep_uniq)

    def expandTemplates(self, keep_uniq=False):
        return self._expand(self.parsed, keep_uniq=keep_uniq)
