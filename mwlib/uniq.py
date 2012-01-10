
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

import os
import re

class Uniquifier(object):
    random_string = None
    rx = None
    def __init__(self):
        self.uniq2repl = {}
        if self.random_string is None:
            import binascii
            r=os.urandom(8)
            self.__class__.random_string = binascii.hexlify(r)
       
    def get_uniq(self, repl, name):
        r = self.random_string
        count = len(self.uniq2repl)
        retval = "\x7fUNIQ-%s-%s-%s-QINU\x7f" % (name, count, r)
        self.uniq2repl[retval] = repl
        return retval
        
    def _repl_from_uniq(self, mo):
        u = mo.group(0)
        t = self.uniq2repl.get(u, None)
        if t is None:
            return u
        return t["complete"]

    def replace_uniq(self, txt):
        rx=re.compile("\x7fUNIQ-[a-z0-9]+-\\d+-[a-f0-9]+-QINU\x7f")
        txt = rx.sub(self._repl_from_uniq, txt)
        return txt
    
    def _repl_to_uniq(self, mo):
        tagname = mo.group("tagname")
        if tagname is None:
            # comment =  mo.group("comment")
            if self.txt[mo.start()]=='\n' and self.txt[mo.end()-1]=='\n':
                return '\n'
            return (mo.group(2) or "")+(mo.group(3) or "")

        else:
            tagname = tagname.lower()
        
        r = dict(
            tagname=tagname,
            inner = mo.group("inner") or u"",
            vlist = mo.group("vlist") or u"",
            complete = mo.group(0) )

        if tagname==u"nowiki":
            r["complete"] = r["inner"]

        return self.get_uniq(r, tagname)
    
    def replace_tags(self, txt):
        self.txt = txt
        rx = self.rx
        if rx is None:
            tags = set("nowiki math imagemap gallery source pre ref timeline poem pages".split())
            from mwlib import tagext
            tags.update(tagext.default_registry.names())

            rx = """
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

            rx = rx.replace("NAMES", "|".join(list(tags)))
            rx = re.compile(rx, re.VERBOSE | re.DOTALL | re.IGNORECASE)
            self.rx = rx 
        newtxt = rx.sub(self._repl_to_uniq, txt)
        return newtxt
