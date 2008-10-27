#! /usr/bin/env python

# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.

import sys

from mwlib.templ import log

from mwlib.templ.nodes import Node, Variable, Template, show
from mwlib.templ.scanner import tokenize
from mwlib.templ.parser import parse, Parser
from mwlib.templ.evaluate import flatten, Expander
from mwlib.templ.misc import DictDB, expandstr

if __name__=="__main__":
    d=unicode(open(sys.argv[1]).read(), 'utf8')
    e = Expander(d)
    print e.expandTemplates()
