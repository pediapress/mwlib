#! /usr/bin/env python

# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

import sys
import os

def caller(n=2):
    """return caller as string"""
    f = sys._getframe(n)
    return "%s:%s" % (f.f_code.co_filename, f.f_lineno)

def short(n=2):
    """return caller as string"""
    f = sys._getframe(n)
    return "%s:%s" % (os.path.basename(f.f_code.co_filename), f.f_lineno)
    
def callerframe(n=2):
    return sys._getframe(n)
