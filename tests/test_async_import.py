#! /usr/bin/env py.test
from mwlib.asynchronous import jobs


def test_async_import():
    jobs.workq
