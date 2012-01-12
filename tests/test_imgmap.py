#! /usr/bin/env py.test

from mwlib import imgmap


def test_whitespace_line():
    s = """image:large.png|Map
# XX
poly 642 127 615 162 635 205 [[Drenthe]]
"""
    map1 = imgmap.ImageMapFromString(s)
    print "MAP1:", map1
    map2 = imgmap.ImageMapFromString(s.replace("# XX", "  "))
    print "MAP2:", map2

    assert map2.image, "missing image"
    assert map2.entries, "missing entries"
