
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

import re

rxc = lambda s: re.compile(s, re.DOTALL | re.IGNORECASE)

onlyincluderx   = rxc("<onlyinclude>(.*?)</onlyinclude>")
noincluderx     = rxc("<noinclude(?:\s[^<>]*)?>.*?(</noinclude>|$)")
includeonlyrx   = rxc("<includeonly(?:\s[^<>]*)?>.*?(?:</includeonly>|$)")


def get_remove_tags(tags):
    r = rxc("</?(%s)(?:\s[^<>]*)?>" % ("|".join(tags)))
    return lambda s: r.sub(u'', s)

remove_not_included = get_remove_tags(["onlyinclude", "noinclude"])


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
