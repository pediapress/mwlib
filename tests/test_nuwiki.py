#! /usr/bin/env py.test
# -*- coding: utf-8 -*-

import os
import shutil
import subprocess
import tempfile

from mwlib.nuwiki import NuWiki

class Test_nuwiki_xnet(object):
    def setup_class(cls):
        cls.tmpdir = tempfile.mkdtemp()
        cls.zipfn = os.path.join(cls.tmpdir, 'test.zip')
        cls.nuwikidir = cls.zipfn + '.nuwiki'
        err = subprocess.call(['mw-zip',
            '-o', cls.zipfn,
            '-c', ':de',
            '--keep-tmpfiles',
            '--print-template-pattern', '$1/Druck',
            '--template-exclusion-category', 'Vom Druck ausschließen',
            'Monty Python',
        ])
        assert os.path.isdir(cls.nuwikidir)
        assert err == 0,  "command failed"
        
    def teardown_class(cls):
        if os.path.exists(cls.tmpdir):
            shutil.rmtree(cls.tmpdir)

    def setup_method(self, method):
        self.nuwiki = NuWiki(self.nuwikidir)

    def test_init(self):
        assert 'Vorlage:ImDruckVerbergen' in self.nuwiki.excluded
        assert 'Monty Python' in self.nuwiki.revisions
        assert self.nuwiki.siteinfo['general']['base'] == 'http://de.wikipedia.org/wiki/Wikipedia:Hauptseite'
        assert self.nuwiki.siteinfo['general']['lang'] == 'de'
        assert self.nuwiki.nshandler is not None
        assert self.nuwiki.nfo['base_url'] == 'http://de.wikipedia.org/w/'
