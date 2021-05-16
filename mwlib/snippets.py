#! /usr/bin/env python

"""provide some mediawiki markup example snippets"""

from __future__ import absolute_import
import os
from six import unichr
import six


class snippet(object):
    def __init__(self, txt, id):
        self.txt = txt
        self.id = id

    def __repr__(self):
        return "<%s %r %r...>" % (self.__class__.__name__, self.id, self.txt[:10])


def get_all():
    fp = os.path.join(os.path.dirname(__file__), 'snippets.txt')

    examples = six.text_type(open(fp).read(), 'utf-8').split(unichr(12) + '\n')[1:]
    res = []
    for i, x in enumerate(examples):
        res.append(snippet(x, i))
    return res
