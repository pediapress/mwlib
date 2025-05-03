#! /usr/bin/env py.test

import time

import gevent
import pytest

from qs.misc import CallInLoop


def throw_error():
    raise RuntimeError("as requested")


def test_iterate_error():
    c = CallInLoop(0.05, throw_error)
    stime = time.time()
    c.iterate()
    needed = time.time() - stime
    assert needed > 0.05


def test_fail_and_restart():
    lst = []

    def doit():
        lst.append(len(lst))
        print("doit", lst)
        if len(lst) == 5:
            raise RuntimeError("size is 5")
        elif len(lst) == 10:
            raise gevent.GreenletExit("done")

    c = CallInLoop(0.001, doit)
    pytest.raises(gevent.GreenletExit, c)
