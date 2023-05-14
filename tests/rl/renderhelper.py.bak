#! /usr/bin/env py.test
# -*- coding: utf-8 -*-

# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.

try:
    import mwlib.ext
except ImportError:
    pass

import os
import tempfile
import re

from PIL import Image, ImageDraw

from reportlab.lib.units import cm
from reportlab.platypus.doctemplate import BaseDocTemplate, NextPageTemplate
from mwlib.rl.pagetemplates import WikiPage

from mwlib import uparser
from mwlib.rl.rlwriter import RlWriter
from mwlib.treecleaner import TreeCleaner
from mwlib import advtree

def renderElements(elements, filesuffix=None, tmpdir=None):
    """ takes a list of reportlab flowables and renders them to a test.pdf file"""
    margin = 2 * cm
    if filesuffix:
        fn = 'test_' + filesuffix + '.pdf'
    else:
        fn = 'test.pdf'
    fn = os.path.join(tmpdir, fn)
    doc = BaseDocTemplate(fn, topMargin=margin, leftMargin=margin, rightMargin=margin, bottomMargin=margin)
    pt = WikiPage("Title")
    doc.addPageTemplates(pt)
    elements.insert(0, NextPageTemplate('Title'))   
    doc.build(elements)

def renderMW(txt, filesuffix=None):
    parseTree = uparser.parseString(title='Test', raw=txt)

    advtree.buildAdvancedTree(parseTree)
    tc = TreeCleaner(parseTree)
    tc.cleanAll()

    tmpdir = tempfile.mkdtemp()    
    rw = RlWriter(test_mode=True)
    rw.wikiTitle = 'testwiki'
    rw.tmpdir = tmpdir
    rw.imgDB = dummyImageDB(basedir=tmpdir)
    elements = rw.write(parseTree)
    renderElements(elements, filesuffix, tmpdir)

class dummyImageDB(object):
    def __init__(self, basedir=None):
        self.basedir = basedir
        self.imgnum = 1

    def _generateImg(self, name='', num=0, size=200):
        img = Image.new('RGB', (size, size))
        d = ImageDraw.Draw(img)
        d.rectangle( [(0,0), img.size] , outline=(255,0,0), fill=(255,0,0))
        
        if num > 0:
            w = img.size[0]/(num*2.0)
            h = img.size[1]
            for i in range(num):
                d.rectangle( [(w*2*i,0), (w*(2*i+1), h)], fill=(0,255,0))
        img.save(name)
    
    def getDiskPath(self, name, size=None):
        res = re.findall('(\d+)', name)
        if res:
            num = int(res[0])
        else:
            num = 0
        name = os.path.join(self.basedir, name)
        self._generateImg(name=name, num=num, size=size)
        self.imgnum+=1
        return name

    def getDescriptionURL(self, name):
        return None

    def getURL(self, name):
        return None
