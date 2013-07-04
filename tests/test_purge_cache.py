#! /usr/bin/env py.test

from mwlib.serve import get_collection_dirs


def test_nested_collection_dirs(tmpdir, monkeypatch):
    tmpdir.join("a" * 16, "b" * 16).ensure(dir=1)
    res = list(get_collection_dirs(tmpdir.strpath))
    print "found", res
    assert res == [tmpdir.join("a" * 16).strpath]
