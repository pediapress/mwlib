#! /usr/bin/env py.test


def test_async_import():
    from mwlib.async import jobs
    jobs.workq
