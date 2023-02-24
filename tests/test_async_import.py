#! /usr/bin/env py.test
from __future__ import absolute_import
from mwlib.asynchronous import jobs


def test_async_import():
    jobs.workq
