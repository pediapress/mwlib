#! /usr/bin/env py.test

import os
import tempfile

import pytest

from mwlib import parser
from mwlib.core import wiki

THE_LIVING_SEA = "The Living Sea"


@pytest.mark.integration
class TestXnetZipWiki:
    zip_filename = None

    @classmethod
    def setup_class(cls):
        fd, cls.zip_filename = tempfile.mkstemp(suffix=".zip")
        os.close(fd)
        print("generating ZIP file")
        rc = os.system(f'mw-zip -c :en -o {cls.zip_filename} "{THE_LIVING_SEA}"')
        print("ZIP file generation finished")
        assert rc == 0, "Could not create ZIP file. Is mw-zip in PATH?"

    @classmethod
    def teardown_class(cls):
        if os.path.exists(cls.zip_filename):
            os.unlink(cls.zip_filename)

    def setup_method(self, method):
        print("reading", self.zip_filename)
        self.env = wiki.make_wiki(self.zip_filename)
        self.wikidb = self.env.wiki
        self.imagedb = self.env.images

    def teardown_method(self, method):
        # self.imagedb.clean()
        pass

    def test_get_article(self):
        a = self.wikidb.normalize_and_get_page(THE_LIVING_SEA, 0)
        assert isinstance(a.rawtext, str)
        assert a.rawtext

    def test_get_parsed_article(self):
        p = self.wikidb.get_parsed_article(THE_LIVING_SEA)
        assert isinstance(p, parser.Article)

    def test_get_url(self):
        url = self.wikidb.get_url(THE_LIVING_SEA)
        assert url == "https://en.wikipedia.org/w/index.php?title=The_Living_Sea"

    def test_image_db(self):
        image_name = "Thelivingseaimax.jpg"
        p = self.imagedb.get_disk_path(image_name)  # returns a symlink to the original image
        assert isinstance(p, str)
        assert os.path.islink(p)
        assert os.lstat(p).st_size > 0
        assert p == self.imagedb.get_disk_path(image_name, 123)

        url = self.imagedb.get_description_url(image_name)
        assert url == "https://en.wikipedia.org/w/index.php?title=File:Thelivingseaimax.jpg"

        templates = self.imagedb.get_image_templates(image_name)
        print(templates)
        assert templates

        contribs = self.imagedb.get_contributors(image_name)
        print(contribs)
        assert contribs

    def test_get_source(self):
        src = self.wikidb.get_source(THE_LIVING_SEA)
        print(src)
