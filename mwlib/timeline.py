#! /usr/bin/env python

# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

"""implement http://meta.wikimedia.org/wiki/EasyTimeline
"""

import os
import tempfile
import subprocess
from hashlib import md5

font = None

def _setupenv():
    global font

    if "GDFONTPATH" in os.environ:
        font = "FreeSans"
        return

    paths = [os.path.expanduser("~/mwlibfonts/freefont"),
             "/usr/share/fonts/TTF",
             "/usr/share/fonts/truetype/freefont"]

    for p in paths:
        if os.path.exists(os.path.join(p, "FreeSans.ttf")):
            os.environ["GDFONTPATH"] = p
            font = "FreeSans"

_setupenv()

_basedir = None
def _get_global_basedir():
    global _basedir
    if not _basedir:
        _basedir = tempfile.mkdtemp(prefix='timeline-')
        import atexit
        import shutil
        atexit.register(shutil.rmtree, _basedir)
    return _basedir

def drawTimeline(script, basedir=None):
    if isinstance(script, unicode):
        script = script.encode('utf8')
    if basedir is None:
        basedir = _get_global_basedir()
        
    m=md5()
    m.update(script)
    ident = m.hexdigest()

    pngfile = os.path.join(basedir, ident+'.png')
    
    if os.path.exists(pngfile):
        return pngfile

    scriptfile = os.path.join(basedir, ident+'.txt')
    open(scriptfile, 'w').write(script)
    et = os.path.join(os.path.dirname(__file__), "EasyTimeline.pl")
    
    err = os.system("perl %s -P /usr/bin/ploticus -f %s -T %s -i %s" % (et, font or "ascii", basedir, scriptfile))
    if err != 0:
        return None

    if os.path.exists(pngfile):
        return pngfile

    return None

    
