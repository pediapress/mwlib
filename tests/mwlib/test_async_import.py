#! /usr/bin/env py.test
from qs import jobs


def test_async_import():
    jobs.workq
