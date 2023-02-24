#! /usr/bin/env py.test

import os
import tempfile

import six

from mwlib import parser, wiki


class Test_xnet_zipwiki(object):
    def setup_class(cls):
        fd, cls.zip_filename = tempfile.mkstemp(suffix=".zip")
        os.close(fd)
        print("generating ZIP file")
        rc = os.system('mw-zip -c :en -o %s "The Living Sea"' % cls.zip_filename)
        print("ZIP file generation finished")
        assert rc == 0, "Could not create ZIP file. Is mw-zip in PATH?"

    def teardown_class(cls):
        if os.path.exists(cls.zip_filename):
            os.unlink(cls.zip_filename)

    def setup_method(self, method):
        print("reading", self.zip_filename)
        self.env = wiki.makewiki(self.zip_filename)
        self.wikidb = self.env.wiki
        self.imagedb = self.env.images

    def teardown_method(self, method):
        # self.imagedb.clean()
        pass

    def test_getArticle(self):
        a = self.wikidb.normalize_and_get_page("The Living Sea", 0)
        assert isinstance(a.rawtext, six.text_type)
        assert a.rawtext

    def test_getParsedArticle(self):
        p = self.wikidb.getParsedArticle("The Living Sea")
        assert isinstance(p, parser.Article)

    def test_getURL(self):
        url = self.wikidb.getURL("The Living Sea")
        assert url == "https://en.wikipedia.org/w/index.php?title=The_Living_Sea"

    def test_ImageDB(self):
        p = self.imagedb.getDiskPath("Thelivingseaimax.jpg")
        assert isinstance(p, six.string_types)
        assert os.path.isfile(p)
        assert os.stat(p).st_size > 0
        assert p == self.imagedb.getDiskPath("Thelivingseaimax.jpg", 123)

        url = self.imagedb.getDescriptionURL("Thelivingseaimax.jpg")
        assert url == "https://en.wikipedia.org/w/index.php?title=File:Thelivingseaimax.jpg"

        templates = self.imagedb.getImageTemplates("Thelivingseaimax.jpg")
        print(templates)
        assert templates

        contribs = self.imagedb.getContributors("Thelivingseaimax.jpg")
        print(contribs)
        assert contribs

    def test_getSource(self):
        src = self.wikidb.getSource("The Living Sea")
        print(src)
