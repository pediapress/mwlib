#! /usr/bin/env python

# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

"""implement http://meta.wikimedia.org/wiki/EasyTimeline
"""

import os
from hashlib import sha1

from mwlib.command.executor import run_perl

font = None


def _setupenv():
    global font

    if "GDFONTPATH" in os.environ:
        font = "FreeSans"
        return

    paths = [
        os.path.expanduser("~/mwlibfonts/freefont"),
        "/usr/share/fonts/TTF",
        "/usr/share/fonts/truetype/freefont",
    ]

    for path in paths:
        if os.path.exists(os.path.join(path, "FreeSans.ttf")):
            os.environ["GDFONTPATH"] = path
            font = "FreeSans"


_setupenv()


def draw_timeline(script, image_nuwiki_dir):
    digest = sha1()
    digest.update(script.encode("utf8"))
    ident = digest.hexdigest()

    pngfile = os.path.join(image_nuwiki_dir, "images", ident + ".png")

    if os.path.exists(pngfile):
        return pngfile
    else:
        raise RuntimeError("could not find %r" % pngfile)
