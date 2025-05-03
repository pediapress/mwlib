#! /usr/bin/env python

# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

"""implement http://meta.wikimedia.org/wiki/EasyTimeline
"""

import os
from hashlib import sha1

font = None


def draw_map_frame(node, image_nuwiki_dir):
    height = node.attributes.get("height", "")
    width = node.attributes.get("width", "")
    latitude = node.attributes.get("latitude", "")
    longitude = node.attributes.get("longitude", "")
    zoom = node.attributes.get("zoom", "")

    digest = sha1()
    identifier = f"{height}x{width}x{latitude}x{longitude}x{zoom}"
    digest.update(identifier.encode("utf8"))
    ident = digest.hexdigest()

    pngfile = os.path.join(image_nuwiki_dir, "images", ident + ".png")

    if os.path.exists(pngfile):
        return pngfile
    else:
        raise RuntimeError("could not find %r" % pngfile)
