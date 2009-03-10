
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.txt for additional licensing information.

import re

rxc = lambda s: re.compile(s, re.DOTALL | re.IGNORECASE)

onlyincluderx   = rxc("<onlyinclude>(.*?)</onlyinclude>")
commentrx       = rxc(r"(\n *)?<!--.*?-->( *\n)?")
noincluderx     = rxc("<noinclude>.*?(</noinclude>|$)")
includeonlyrx   = rxc("<includeonly>.*?(?:</includeonly>|$)")

def get_remove_tags(tags):
    r=rxc("</?(%s)>" % ("|".join(tags)))
    return lambda s: r.sub(u'', s)

remove_not_included = get_remove_tags(["onlyinclude", "noinclude"])


def remove_comments(txt):
    def repl(m):
        #print "M:", repr(txt[m.start():m.end()])
        if txt[m.start()]=='\n' and txt[m.end()-1]=='\n':
            return '\n'
        return (m.group(1) or "")+(m.group(2) or "")
    return commentrx.sub(repl, txt)

def preprocess(txt, included=True):
    if included:
        txt = noincluderx.sub(u'', txt)

        if "<onlyinclude>" in txt:
            # if onlyinclude tags are used, only use text between those tags. template 'legend' is a example
            txt = "".join(onlyincluderx.findall(txt))
    else:
        txt = includeonlyrx.sub(u'', txt)
        txt = remove_not_included(txt)
    
    return txt
