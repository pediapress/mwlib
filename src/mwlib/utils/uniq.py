# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.


import os
import re


class Uniquifier:
    random_string = None
    regex_pattern = None

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

    def _repl_from_uniq(self, matched_pattern):
        uniq = matched_pattern.group(0)
        replacement_data = self.uniq2repl.get(uniq, None)
        if replacement_data is None:
            return uniq
        return replacement_data["complete"]

    def replace_uniq(self, txt):
        compiled_regex = re.compile("\x7fUNIQ-[a-z0-9]+-\\d+-[a-f0-9]+-QINU\x7f")
        txt = compiled_regex.sub(self._repl_from_uniq, txt)
        return txt

    def _repl_to_uniq(self, matched_pattern):
        tagname = matched_pattern.group("tagname")
        if tagname is None:
            if (
                self.txt[matched_pattern.start()] == "\n"
                and self.txt[matched_pattern.end() - 1] == "\n"
            ):
                return "\n"
            return (matched_pattern.group(2) or "") + (matched_pattern.group(3) or "")

        else:
            tagname = tagname.lower()

        result = {
            "tagname": tagname,
            "inner": matched_pattern.group("inner") or "",
            "vlist": matched_pattern.group("vlist") or "",
            "complete": matched_pattern.group(0),
        }

        if tagname == "nowiki":
            result["complete"] = result["inner"]

        return self.get_uniq(result, tagname)

    def replace_tags(self, txt):
        self.txt = txt
        regex_pattern = self.regex_pattern
        if regex_pattern is None:
            tags = set(
                ["nowiki", "math", "imagemap", "gallery", "source", "pre", "ref", "timeline", "poem", "pages"]
            )
            from mwlib.parser import tagext

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
            self.regex_pattern = regex_pattern
        newtxt = regex_pattern.sub(self._repl_to_uniq, txt)
        return newtxt
