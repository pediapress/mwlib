#! /usr/bin/env py.test
# -*- coding: utf-8 -*-

import os
import shutil
import subprocess
import tempfile
import zipfile

from mwlib.nuwiki import adapt


class Test_nuwiki_xnet(object):
    def setup_class(cls):
        cls.tmpdir = tempfile.mkdtemp()
        cls.zipfn = os.path.join(cls.tmpdir, 'test.zip')
        err = subprocess.call(['mw-zip',
            '-o', cls.zipfn,
            '-c', ':de',
            '--print-template-pattern', '$1/Druck',
            '--template-exclusion-category', 'Vom Druck ausschließen',
            'Monty Python',
        ])
        assert os.path.isfile(cls.zipfn)
        assert err == 0,  "command failed"

    def teardown_class(cls):
        if os.path.exists(cls.tmpdir):
            shutil.rmtree(cls.tmpdir)

    def setup_method(self, method):
        self.nuwiki = adapt(zipfile.ZipFile(self.zipfn, 'r')).nuwiki

    def test_init(self):
        assert 'Vorlage:Navigationsleiste' in self.nuwiki.excluded
        assert 'Monty Python' in self.nuwiki.revisions
        assert self.nuwiki.siteinfo['general']['base'] == 'http://de.wikipedia.org/wiki/Wikipedia:Hauptseite'
        assert self.nuwiki.siteinfo['general']['lang'] == 'de'
        assert self.nuwiki.nshandler is not None
        assert self.nuwiki.nfo['base_url'] == 'http://de.wikipedia.org/w/'
