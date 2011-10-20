#! /usr/bin/env python

# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

import sys

from mwlib.templ import log

from mwlib.templ.nodes import Node, Variable, Template, show
from mwlib.templ.scanner import tokenize
from mwlib.templ.parser import parse, Parser
from mwlib.templ.evaluate import flatten, Expander, ArgumentList
from mwlib.templ.misc import DictDB, expandstr


def get_templates(raw, title=u""):
    used = set()
    e=Expander('', wikidb=DictDB())
    todo = [parse(raw, replace_tags=e.replace_tags)]
    while todo:
        n = todo.pop()
        if isinstance(n, basestring):
            continue
        
        if isinstance(n, Template) and isinstance(n[0], basestring):
            name = n[0]
            if name.startswith("/"):
                name = title+name
            used.add(name)
            
        todo.extend(n)
        
    return used

def find_template(raw, name, parsed_raw=None):
    """Return Template node with given name or None if there is no such template"""
    
    if not parsed_raw:
        e=Expander('', wikidb=DictDB())
        todo = [parse(raw, replace_tags=e.replace_tags)]
    else:
        todo = parsed_raw
    while todo:
        n = todo.pop()
        if isinstance(n, basestring):
            continue
        if isinstance(n, Template) and isinstance(n[0], basestring):
            if n[0] == name:
                return n
        todo.extend(n)

def get_template_args(template, expander):
    """Return ArgumentList for given template"""
    
    return ArgumentList(template[1],
        expander=expander,
        variables=ArgumentList(expander=expander),
    )
    

if __name__=="__main__":
    d=unicode(open(sys.argv[1]).read(), 'utf8')
    e = Expander(d)
    print e.expandTemplates()
