#! /usr/bin/env python

"""This is the "CGI equivalent" of mw-serve. Adjust the configuration variables
below and install this script as CGI script for your web server.
"""

# Configuration:

# Name of logfile or None if log output should go to stderr.
LOGFILE = None
#LOGFILE = '/var/log/mwlib.cgi.log'

# Cache directory. Must be writeable.
CACHE_DIR = '/var/cache/mwlib/'

# (Path to) mw-render executable.
MWRENDER = 'mw-render'

# Logfile for mw-render.
MWRENDER_LOGFILE = '/var/log/mw-render.log'

# (Path to) mw-zip executable.
MWZIP = 'mw-zip'

# Logfile for mw-zip.
MWZIP_LOGFILE = '/var/log/mw-zip.log'

# (Path to) mw-post executable.
MWPOST = 'mw-post'

# Logfile for mw-post.
MWPOST_LOGFILE = '/var/log/mw-post.log'

# Queue directory for mw-watch or None if no queue should be used
QUEUE_DIR = None
#QUEUE_DIR = '/var/cache/mw-watch/q'

# ==============================================================================

import os
import sys

from flup.server.cgi import WSGIServer

from mwlib import serve, utils

if os.name == 'nt':
    import msvcrt
    if hasattr(sys.stdout, 'fileno') and sys.stdout.fileno() >= 0:
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)

if LOGFILE is not None:
    utils.start_logging(LOGFILE, stderr_only=True)

WSGIServer(serve.Application(
    cache_dir=CACHE_DIR,
    mwrender_cmd=MWRENDER,
    mwrender_logfile=MWRENDER_LOGFILE,
    mwzip_cmd=MWZIP,
    mwzip_logfile=MWZIP_LOGFILE,
    mwpost_cmd=MWPOST,
    mwpost_logfile=MWPOST_LOGFILE,
    queue_dir=QUEUE_DIR,
)).run()
