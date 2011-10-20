#! /usr/bin/env python

# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

from mwlib import parser

def simplify(node, **kwargs):
    "concatenates textnodes in order to reduce the number of objects"
    Text = parser.Text
    
    last = None
    toremove = []
    for i,c in enumerate(node.children):
        if c.__class__ == Text: # would isinstance be safe?
            if last:
                last.caption += c.caption
                toremove.append(i)
            else:
                last = c
        else:
            simplify(c)
            last = None

    for i,ii in enumerate(toremove):
        del node.children[ii-i]


def removeBoilerplate(node, **kwargs):
    i = 0
    while i < len(node.children):
        x = node.children[i]
        if isinstance(x, parser.TagNode) and x.caption=='div':
            try:
                klass = x.values.get('class', '')
            except AttributeError:
                klass = ''
                
            if 'boilerplate' in klass:
                del node.children[i]
                continue
            
        i += 1

    for x in node.children:
        removeBoilerplate(x)


postprocessors = [removeBoilerplate, simplify]
