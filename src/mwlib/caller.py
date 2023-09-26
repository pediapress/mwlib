#! /usr/bin/env python

# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.


import os
import sys


def caller(frame_depth=2):
    """return caller as string"""
    frame = sys._getframe(frame_depth)
    return f"{frame.f_code.co_filename}:{frame.f_lineno}"


def short(frame_depth=2):
    """return caller as string"""
    frame = sys._getframe(frame_depth)
    return f"{os.path.basename(frame.f_code.co_filename)}:{frame.f_lineno}"


def callerframe(frame_depth=2):
    return sys._getframe(frame_depth)
