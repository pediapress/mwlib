
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.txt for additional licensing information.

import re

class Uniquifier(object):
    random_string = None 
    def __init__(self):
        self.uniq2repl = {}
        
    def get_uniq(self, repl, name):
        r = self.get_random_string()
        count = len(self.uniq2repl)
        retval = "\x7fUNIQ-%s-%s-%s-QINU\x7f" % (name, count, r)
        self.uniq2repl[retval] = repl
        return retval
    
        
    def get_random_string(self):
        if self.random_string is None:
            import binascii
            r=open("/dev/urandom").read(8)
            self.__class__.random_string = binascii.hexlify(r)
        return self.random_string

    def _repl_from_uniq(self, mo):
        
        u = mo.group(0)
        return self.uniq2repl.get(u, u)

    def replace_uniq(self, txt):
        rx=re.compile("\x7fUNIQ-[a-z]+-\\d+-[a-f0-9]+-QINU\x7f")
        txt = rx.sub(self._repl_from_uniq, txt)
        return txt
    
    def _repl_to_uniq(self, mo):
        for name, s in mo.groupdict().items():
            if s:
                return self.get_uniq(s, name)
        assert 0
        # print "GROUPS:", mo.groupdict()
        # return self.get_uniq(mo.group(0))
    
    def replace_tags(self, txt):
        rx=re.compile("""(?P<nowiki><nowiki>.*?</nowiki>)          # nowiki
|(?P<math><math>.*?</math>)
|(?P<imagemap><imagemap[^<>]*>.*?</imagemap>)
|(?P<gallery><gallery[^<>]*>.*?</gallery>)
|(?P<ref><ref[^<>]*/?>)
|(?P<source><source[^<>]*>.*?</source>)
|(?P<pre><pre.*?>.*?</pre>)""", re.VERBOSE | re.DOTALL | re.IGNORECASE)
        newtxt = rx.sub(self._repl_to_uniq, txt)
        return newtxt
