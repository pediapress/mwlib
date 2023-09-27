# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.


import os
import re


class Uniquifier:
    random_string = None
    rx = None

    def __init__(self):
        self.uniq2repl = {}
        if self.random_string is None:
            import binascii

            rand_hex = os.urandom(8)
            self.__class__.random_string = binascii.hexlify(rand_hex).decode("utf8")

    def get_uniq(self, repl, name):
        rand_string = self.random_string
        count = len(self.uniq2repl)
        retval = f"\x7fUNIQ-{name}-{count}-{rand_string}-QINU\x7f"
        self.uniq2repl[retval] = repl
        return retval

    def _repl_from_uniq(self, mo):
        uniq = mo.group(0)
        t = self.uniq2repl.get(uniq, None)
        if t is None:
            return uniq
        return t["complete"]

    def replace_uniq(self, txt):
        rx = re.compile("\x7fUNIQ-[a-z0-9]+-\\d+-[a-f0-9]+-QINU\x7f")
        txt = rx.sub(self._repl_from_uniq, txt)
        return txt

    def _repl_to_uniq(self, mo):
        tagname = mo.group("tagname")
        if tagname is None:
            if self.txt[mo.start()] == "\n" and self.txt[mo.end() - 1] == "\n":
                return "\n"
            return (mo.group(2) or "") + (mo.group(3) or "")

        else:
            tagname = tagname.lower()

        r = {
            "tagname": tagname,
            "inner": mo.group("inner") or "",
            "vlist": mo.group("vlist") or "",
            "complete": mo.group(0),
        }

        if tagname == "nowiki":
            r["complete"] = r["inner"]

        return self.get_uniq(r, tagname)

    def replace_tags(self, txt):
        self.txt = txt
        regex_pattern = self.rx
        if regex_pattern is None:
            tags = set(
                "nowiki math imagemap gallery source pre ref timeline poem pages".split()
            )
            from mwlib import tagext

            tags.update(tagext.default_registry.names())

            regex_pattern = """
                (?P<comment> (\\n[ ]*)?<!--.*?-->([ ]*\\n)?) |
                (?:
                <(?P<tagname> NAMES)
                (?P<vlist> \\s[^<>]*)?
                (/>
                 |
                 (?<!/) >
                (?P<inner>.*?)
                </(?P=tagname)\\s*>))
            """

            regex_pattern = regex_pattern.replace("NAMES", "|".join(list(tags)))
            regex_pattern = re.compile(
                regex_pattern, re.VERBOSE | re.DOTALL | re.IGNORECASE
            )
            self.rx = regex_pattern
        newtxt = regex_pattern.sub(self._repl_to_uniq, txt)
        return newtxt
