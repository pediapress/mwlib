
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
            r = "(?P<%s>" % name
            r += "<%s" % name
            r += "(?P<%s_vlist>" % name
            r += "\\s[^<>]*)?>"
            r += "(?P<%s_inner>.*?)" % name
            r += ">"
            r += "</%s>)" % name
            tags.append(r)
            

        add_tag("math")
        add_tag("imagemap")
        add_tag("gallery")
        add_tag("source")
        add_tag("pre")
        add_tag("ref")
        
        rx =  '|'.join(tags)
        if 1:
            print rx
            rx = re.compile(rx)
            newtxt = rx.sub(self._repl_to_uniq, txt)
            return newtxt

            
        rx=re.compile("""(?:<nowiki>(?P<nowiki>.*?)</nowiki>)          # nowiki
|(?P<math><math>(?P<math_inner>.*?)</math>)
|(?P<imagemap><imagemap[^<>]*>(?P<imagemap_inner>.*?)</imagemap>)
|(?P<gallery><gallery(?P<gallery_vlist>[^<>]*)>(?P<gallery_inner>.*?)</gallery>)
|(?P<ref><ref[^<>]*/?>)
|(?P<source><source[^<>]*>(?P<source_inner>.*?)</source>)
|(?P<pre><pre.*?>(?P<pre_inner>.*?)</pre>)""", re.VERBOSE | re.DOTALL | re.IGNORECASE)
        newtxt = rx.sub(self._repl_to_uniq, txt)
        return newtxt
