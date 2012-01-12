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
    data = utils.report(system='system123', subject='subject123', foo='foo123')
    assert 'foo' in data
    assert 'foo123' in data


def test_get_safe_url():
    g = utils.get_safe_url
    assert g('http://bla" target="_blank') is None
    assert g('http') is None
    assert g('http://bla/foo/bar" target="_blank') == 'http://bla/foo/bar%22%20target%3D%22_blank'
    assert g(u'http://xyz/wiki/%D0%91%D0%94%D0%A1%D0%9C') == 'http://xyz/wiki/%D0%91%D0%94%D0%A1%D0%9C'


def test_garble_password():
    x = utils.garble_password(['foo', '--password', 'secret'])
    assert 'secret' not in x
    utils.garble_password(['foo', '--password'])
    utils.garble_password(['foo'])
