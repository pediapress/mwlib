#! /usr/bin/env py.test
# -*- coding: utf-8 -*-

# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.

from renderhelper import renderMW
from mwlib import snippets

def doit(ex):
    print "rendering", ex
    renderMW(ex.txt)
    
def test_examples():
    s=snippets.get_all()
    for x in s:
        yield doit, x
