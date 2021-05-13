#! /usr/bin/env py.test


def test_async_import():
    from mwlib.asynchronous import jobs
    jobs.workq
