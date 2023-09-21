#! /usr/bin/env python
"""provide some mediawiki markup example snippets"""

import os


class Snippet:
    def __init__(self, txt, snippet_id):
        self.txt = txt
        self.id = snippet_id

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.id!r} {self.txt[:10]!r}...>"


def get_all():
    # FIXME: turn this into a py.text fixture
    fn = os.path.join(os.path.dirname(__file__), "snippets.txt")
    with open(fn) as snippet_file:
        examples = snippet_file.read().split("\x0c\n")[1:]
    res = []
    for i, example in enumerate(examples):
        res.append(Snippet(example, i))
    return res
