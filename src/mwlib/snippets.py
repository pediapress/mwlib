#! /usr/bin/env python
"""provide some mediawiki markup example snippets"""

import os


class snippet:
    def __init__(self, txt, id):
        self.txt = txt
        self.id = id

    def __repr__(self):
        return "<%s %r %r...>" % (self.__class__.__name__, self.id, self.txt[:10])


def get_all():
    # FIXME: turn this into a py.text fixture
    fn = os.path.join(os.path.dirname(__file__), "snippets.txt")
    with open(fn, "r") as f:
        examples = f.read().split("\x0c\n")[1:]
    res = []
    for i, x in enumerate(examples):
        res.append(snippet(x, i))
    return res
