#! /usr/bin/env python

# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

import sys

import six

from mwlib.templ import log

from mwlib.templ.nodes import Node, Variable, Template, show
from mwlib.templ.scanner import tokenize
from mwlib.templ.parser import parse, Parser
from mwlib.templ.evaluate import flatten, Expander, ArgumentList
from mwlib.templ.misc import DictDB, expand_str


def get_templates(raw, title=""):
    used = set()
    expander = Expander('', wikidb=DictDB())
    todo = [parse(raw, replace_tags=expander.replace_tags)]
    while todo:
        node = todo.pop()
        if isinstance(node, six.string_types):
            continue

        if isinstance(node, Template) and isinstance(node[0], six.string_types):
            name = node[0]
            if name.startswith("/"):
                name = title + name
            used.add(name)

        todo.extend(node)

    return used


def find_template(raw, name, parsed_raw=None):
    """Return Template node with given
    name or None if there is no such template"""

    if not parsed_raw:
        e = Expander('', wikidb=DictDB())
        todo = [parse(raw, replace_tags=e.replace_tags)]
    else:
        todo = parsed_raw
    while todo:
        node = todo.pop()
        if isinstance(node, six.string_types):
            continue
        if isinstance(node,
                      Template) and isinstance(node[0],
                                               six.string_types) and node[0] == name:
            return node
        todo.extend(node)


def get_template_args(template, expander):
    """Return ArgumentList for given template"""

    return ArgumentList(template[1],
                        expander=expander,
                        variables=ArgumentList(expander=expander),
                        )


if __name__ == "__main__":
    with open(sys.argv[1], 'rb') as f:
        d = f.read()
    d = six.text_type(open(sys.argv[1]).read(), 'utf8')
    e = Expander(d)
    print(e.expandTemplates())
