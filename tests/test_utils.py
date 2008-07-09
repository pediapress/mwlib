#! /usr/bin/env py.test
# -*- coding: utf-8 -*-

"""Unittests for mwlib.utils"""

import os

from mwlib import utils

def test_fsescape():
    test_set = (
        (u'abc', 'abc'),
        ('abc', 'abc'),
        (u'ä', '~228~'),
        ('ä', '~195~~164~'),
        (u'~', '~~'),
        ('~', '~~'),
    )
    for s_in, s_out in test_set:
        assert utils.fsescape(s_in) == s_out
        assert type(utils.fsescape(s_in)) is str

def test_uid():
    uids = set()
    for i in range(100):
        uid = utils.uid()
        assert uid not in uids
        uids.add(uid)
    for max_length in range(1, 20):
        assert len(utils.uid(max_length)) <= max_length

def test_report():
    filename = utils.report(system='system123', subject='subject123', foo='foo123')
    data = open(filename, 'rb').read().lower()
    for s in ('system', 'subject', 'foo'):
        assert s in data
        assert s + '123' in data
    os.unlink(filename)
    p = os.path.expanduser('~/errors/')
    files = os.listdir(p)
    if not files:
        os.rmdir(p)
