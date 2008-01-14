#! /usr/bin/env py.test

from mwlib import imgmap

def test_whitespace_line():
    s="image:large.png|Map\n  poly 642 127 615 162 635 205 [[Drenthe]]\n"
    imgmap.ImageMapFromString(s)
