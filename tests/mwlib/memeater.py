#! /usr/bin/env python

from mwlib.expander import DictDB
from mwlib.templ.misc import expand_str

d4 = """
{{#if:{{{inline|}}} | dfklghsldfkghslkdfghslkdfjhglskjdfghlskjdfg }}

{{d4|
Image: {{{1}}}
{{#if:{{{Masse|}}}{{{4|}}}|{{{Masse|{{{4}}}}}}}}
{{{Alt|{{{Titel|{{{3|{{{Ziel|{{{2|&nbsp;}}}}}}}}}}}}}}}
{{#if:{{{Ziel|}}}{{{2|}}}
 |
default [[{{{Ziel|{{{2}}}}}}|{{{Titel|{{{Ziel|{{{2}}}}}}}}}]]
 |{{#if:{{{Formen|}}}
  |
  |default [[Bild:{{{Bild|{{{1}}}}}}]]
}}}}
}}
"""


def main():
    db = DictDB(d4=d4)
    expand_str(d4, wikidb=db)


if __name__ == "__main__":
    main()
