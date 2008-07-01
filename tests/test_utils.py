#! /usr/bin/env py.test
# -*- coding: utf-8 -*-

"""Unittests for mwlib.utils"""

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
