#! /usr/bin/env python

# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

"""implement http://meta.wikimedia.org/wiki/EasyTimeline
"""

import atexit
import os
import shutil
import tempfile
from hashlib import sha256

from mwlib.command.executor import run_perl

font = None


def _setupenv():
    global font

    if "GDFONTPATH" in os.environ:
        font = "FreeSans"
        return

    paths = [os.path.expanduser("~/mwlibfonts/freefont"),
             "/usr/share/fonts/TTF",
             "/usr/share/fonts/truetype/freefont"]

    for path in paths:
        if os.path.exists(os.path.join(path, "FreeSans.ttf")):
            os.environ["GDFONTPATH"] = path
            font = "FreeSans"


_setupenv()

_BASEDIR = None


def _get_global_basedir():
    global _BASEDIR
    if not _BASEDIR:
        _BASEDIR = tempfile.mkdtemp(prefix='timeline-')
        atexit.register(shutil.rmtree, _BASEDIR)
    return _BASEDIR


def draw_timeline(script, basedir=None):
    if basedir is None:
        basedir = _get_global_basedir()

    digest = sha256()
    digest.update(script.encode('utf8'))
    ident = digest.hexdigest()

    pngfile = os.path.join(basedir, ident + '.png')

    if os.path.exists(pngfile):
        return pngfile

    script_filepath = os.path.join(basedir, ident + '.txt')
    with open(script_filepath, 'w', encoding='utf-8') as script_file:
        script_file.write(script)
    easy_timeline_path = os.path.join(os.path.dirname(__file__), "EasyTimeline.pl")

    return run_perl(easy_timeline_path, font, basedir, script_filepath, pngfile)
