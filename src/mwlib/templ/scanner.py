# Copyright (c) 2007-2009 PediaPress GmbH
# See README.md for additional licensing information.

from __future__ import absolute_import

import re

from mwlib.templ import pp

splitpattern = """
({{+)                     # opening braces
|(}}+)                    # closing braces
|(\[\[|\]\])              # link
|((?:<noinclude>.*?</noinclude>)|(?:</?includeonly>))  # noinclude, comments: usually ignore
|(?P<text>(?:<nowiki>.*?</nowiki>)          # nowiki
|(?:<math>.*?</math>)
|(?:<imagemap[^<>]*>.*?</imagemap>)
|(?:<gallery[^<>]*>.*?</gallery>)
|(?:<ref[^<>]*/>)
|(?:<source[^<>]*>.*?</source>)
|(?:<pre.*?>.*?</pre>)
|(?:=)
|(?:[\[\]\|{}<])                                  # all special characters
|(?:[^=\[\]\|{}<]*))                               # all others
"""

split_rx = re.compile(splitpattern, re.VERBOSE | re.DOTALL | re.IGNORECASE)


class Symbols:
    bra_open = 1
    bra_close = 2
    link = 3
    noi = 4
    txt = 5


def tokenize(txt, included=True, replace_tags=None):
    txt = pp.preprocess(txt, included=included)

    if replace_tags is not None:
        txt = replace_tags(txt)

    tokens = []
    for (v1, v2, v3, v4, v5) in split_rx.findall(txt):
        if v5:
            tokens.append((5, v5))
        elif v4:
            tokens.append((4, v4))
        elif v3:
            tokens.append((3, v3))
        elif v2:
            tokens.append((2, v2))
        elif v1:
            tokens.append((1, v1))

    tokens.append((None, ""))

    return tokens
