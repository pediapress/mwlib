#! /usr/bin/env python

# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

import sys
import time

class Stdout(object):
    """late-bound sys.stdout"""
    def write(self, msg):
        sys.stdout.write(msg)

    def flush(self):
        sys.stdout.flush()

class Stderr(object):
    """late-bound sys.stderr"""
    def write(self, msg):
        sys.stderr.write(msg)

    def flush(self):
        sys.stderr.flush()

class Log(object):
    logfile = Stderr()
    timestamp_fmt = '%Y-%m-%dT%H:%M:%S'
    
    def __init__(self, prefix=None, timestamps=True):
        self.timestamps = timestamps
        if prefix is None:
            self._prefix = []
        else:
            if isinstance(prefix, basestring):
                self._prefix = [prefix]
            else:
                self._prefix = prefix

    def __getattr__(self, name):
        return Log([self, name], timestamps=self.timestamps)

    def __nonzero__(self):
        return bool(self._prefix)
    
    def __str__(self):
        return ".".join(str(x) for x in self._prefix if x)
                 
    def __call__(self, msg, *args):
        if not self.logfile:
            return
        
        if not isinstance(msg, str):
            msg = repr(msg)
        
        if args:
            msg = " ".join(([msg] + [repr(x) for x in args]))
        
        s = ''
        if self.timestamps:
            s = '%s ' % time.strftime(self.timestamp_fmt)
        s += "%s >> %s\n" % (".".join(str(x) for x in self._prefix if x), msg)
        self.logfile.write(s)
