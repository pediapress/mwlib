#! /usr/bin/env py.test

import os
import shutil
import subprocess
import tempfile
import zipfile

import pytest

from mwlib.nuwiki import Adapt


@pytest.mark.integration
class TestNuwikiXnet:
    @classmethod
    def setup_class(cls):
        cls.tmpdir = tempfile.mkdtemp()
        cls.zip_fn = os.path.join(cls.tmpdir, "test.zip")
        err = subprocess.call(
            [
                "mw-zip",
                "-o",
                cls.zip_fn,
                "-c",
                ":de",
                "Monty Python",
            ]
        )
        assert os.path.isfile(cls.zip_fn)
        assert err == 0, "command failed"

    @classmethod
    def teardown_class(cls):
        if os.path.exists(cls.tmpdir):
            shutil.rmtree(cls.tmpdir)

    def setup_method(self, method):
        self.nuwiki = Adapt(zipfile.ZipFile(self.zip_fn, "r")).nuwiki

    def test_init(self):
        assert "Monty Python" in self.nuwiki.revisions
        assert (
            self.nuwiki.siteinfo["general"]["base"]
            == "https://de.wikipedia.org/wiki/Wikipedia:Hauptseite"
        )
        assert self.nuwiki.siteinfo["general"]["lang"] == "de"
        assert self.nuwiki.nshandler is not None
        assert self.nuwiki.nfo["base_url"] == "https://de.wikipedia.org/w/"
