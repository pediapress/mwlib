# ! /usr/bin/env py.test
# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.


import os
import re
import tempfile

from PIL import Image, ImageDraw
from reportlab.lib.units import cm
from reportlab.platypus.doctemplate import BaseDocTemplate, NextPageTemplate

from mwlib.parser import advtree
from mwlib.parser.refine import uparser
from mwlib.parser.treecleaner import TreeCleaner
from mwlib.writers.rl.pagetemplates import WikiPage
from mwlib.writers.rl.writer import RlWriter


def renderElements(elements, filesuffix=None, tmpdir=None):
    """takes a list of reportlab flowables and renders them to a test.pdf file"""
    margin = 2 * cm
    fn = "test_" + filesuffix + ".pdf" if filesuffix else "test.pdf"
    fn = os.path.join(tmpdir, fn)
    doc = BaseDocTemplate(
        fn, topMargin=margin, leftMargin=margin, rightMargin=margin, bottomMargin=margin
    )
    pt = WikiPage("Title")
    doc.addPageTemplates(pt)
    elements.insert(0, NextPageTemplate("Title"))
    doc.build(elements)


def renderMW(txt, filesuffix=None):
    parseTree = uparser.parse_string(title="Test", raw=txt)

    advtree.build_advanced_tree(parseTree)
    tc = TreeCleaner(parseTree)
    tc.clean_all()

    tmpdir = tempfile.mkdtemp()
    rw = RlWriter(test_mode=True)
    rw.wikiTitle = "testwiki"
    rw.tmpdir = tmpdir
    rw.imgDB = dummyImageDB(basedir=tmpdir)
    elements = rw.write(parseTree)
    renderElements(elements, filesuffix, tmpdir)


class dummyImageDB:
    def __init__(self, basedir=None):
        self.basedir = basedir
        self.imgnum = 1

    def _generateImg(self, name="", num=0, size=200):
        img = Image.new("RGB", (size, size))
        d = ImageDraw.Draw(img)
        d.rectangle([(0, 0), img.size], outline=(255, 0, 0), fill=(255, 0, 0))

        if num > 0:
            w = img.size[0] / (num * 2.0)
            h = img.size[1]
            for i in range(num):
                d.rectangle([(w * 2 * i, 0), (w * (2 * i + 1), h)], fill=(0, 255, 0))
        img.save(name)

    def get_disk_path(self, name, size=None):
        res = re.findall(r"(\d+)", name)
        num = int(res[0]) if res else 0
        name = os.path.join(self.basedir, name)
        self._generateImg(name=name, num=num, size=size)
        self.imgnum += 1
        return name

    def get_description_url(self, name):
        return None

    def get_url(self, name):
        return None
