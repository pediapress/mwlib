
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.txt for additional licensing information.

import re

class Uniquifier(object):
    random_string = None 
    def __init__(self):
        self.uniq2repl = {}
        if self.random_string is None:
            import binascii
            r=open("/dev/urandom").read(8)
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
        return t[1]

    def replace_uniq(self, txt):
        rx=re.compile("\x7fUNIQ-[a-z]+-\\d+-[a-f0-9]+-QINU\x7f")
        txt = rx.sub(self._repl_from_uniq, txt)
        return txt
    
    def _repl_to_uniq(self, mo):
        groupdict = mo.groupdict()
        for name, s in groupdict.items():
            if s and "_" not in name:
                return self.get_uniq((name, s, groupdict), name)
        assert 0
    
    def replace_tags(self, txt):

        tags = ["(?:<nowiki>(?P<nowiki>.*?)</nowiki>)"]
        def add_tag(name):
            r = """(?P<NAME>
            <NAME
            (?P<NAME_vlist> \\s[^<>]*)?
            (/>
             |
             (?<!/) >
            (?P<NAME_inner>.*?)
            </NAME>))
"""
            
            tags.append(r.replace("NAME", name))
            

        add_tag("math")
        add_tag("imagemap")
        add_tag("gallery")
        add_tag("source")
        add_tag("pre")
        add_tag("ref")
        add_tag("timeline")
        
        rx =  '\n|\n'.join(tags)
        rx = re.compile(rx, re.VERBOSE | re.DOTALL | re.IGNORECASE)
        newtxt = rx.sub(self._repl_to_uniq, txt)
        return newtxt
