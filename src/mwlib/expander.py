#! /usr/bin/env python

# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

import sys

import six

from mwlib.templ.evaluate import ArgumentList, Expander
from mwlib.templ.misc import DictDB
from mwlib.templ.nodes import Template
from mwlib.templ.parser import parse


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
        exp = Expander('', wikidb=DictDB())
        todo = [parse(raw, replace_tags=exp.replace_tags)]
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
    return None


def get_template_args(template, expander):
    """Return ArgumentList for given template"""

    return ArgumentList(template[1],
                        expander=expander,
                        variables=ArgumentList(expander=expander),
                        )


if __name__ == "__main__":
    with open(sys.argv[1], 'rb', encoding='utf-8') as f:
        d = six.text_type(f.read(), 'utf8')
    e = Expander(d)
    print(e.expandTemplates())
