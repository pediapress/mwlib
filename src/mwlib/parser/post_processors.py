#! /usr/bin/env python

# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.


from mwlib import parser


def simplify(node, **kwargs):
    "concatenates textnodes in order to reduce the number of objects"
    Text = parser.Text

    last = None
    toremove = []
    for i, child in enumerate(node.children):
        if child.__class__ == Text:  # would isinstance be safe?
            if last:
                last.caption += child.caption
                toremove.append(i)
            else:
                last = child
        else:
            simplify(child)
            last = None

    for i, index in enumerate(toremove):
        del node.children[index - i]


def remove_boilerplate(node, **kwargs):
    i = 0
    while i < len(node.children):
        child = node.children[i]
        if isinstance(child, parser.TagNode) and child.caption == 'div':
            try:
                klass = child.values.get('class', '')
            except AttributeError:
                klass = ''

            if 'boilerplate' in klass:
                del node.children[i]
                continue

        i += 1

    for child_node in node.children:
        remove_boilerplate(child_node)


postprocessors = [remove_boilerplate, simplify]
