# Copyright (c) 2007-2009 PediaPress GmbH
# See README.md for additional licensing information.

import re

from mwlib.templ import pp

SPLIT_PATTERN = r"""
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

split_rx = re.compile(SPLIT_PATTERN, re.VERBOSE | re.DOTALL | re.IGNORECASE)


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
    for token_type_1, token_type_2, token_type_3, token_type_4, token_type_5 in split_rx.findall(txt):
        if token_type_5:
            tokens.append((5, token_type_5))
        elif token_type_4:
            tokens.append((4, token_type_4))
        elif token_type_3:
            tokens.append((3, token_type_3))
        elif token_type_2:
            tokens.append((2, token_type_2))
        elif token_type_1:
            tokens.append((1, token_type_1))

    tokens.append((None, ""))

    return tokens
