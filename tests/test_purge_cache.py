#! /usr/bin/env py.test

import os, shutil, errno, time, pytest
from mwlib.serve import \
    get_collection_dirs, _rmtree, _find_collection_dirs_to_purge, purge_cache


@pytest.fixture
def tree(tmpdir):
    tmpdir.join("a"*16).ensure(dir=1)
    tmpdir.join("b"*16, "collection.zip").ensure()
    return sorted(get_collection_dirs(tmpdir.strpath))


def test_nested_collection_dirs(tmpdir, monkeypatch):
    tmpdir.join("a" * 16, "b" * 16).ensure(dir=1)
    res = list(get_collection_dirs(tmpdir.strpath))
    print "found", res
    assert res == [tmpdir.join("a" * 16).strpath]


def test_rmtree_nonexistent(tmpdir):
    _rmtree(tmpdir.join("foobar").strpath)


def test_rmtree_other_error(tmpdir, monkeypatch):
    def permdenied(_):
        raise OSError(errno.EPERM, "permission denied")
    monkeypatch.setattr(shutil, "rmtree", permdenied)
    _rmtree(tmpdir.strpath)


def test_rmtree(tmpdir):
    dirpath = tmpdir.join("foo")
    dirpath.ensure(dir=1)
    _rmtree(dirpath.strpath)
    assert not dirpath.check()


def test_find_collection_dirs_to_purge(tmpdir, tree):
    now = time.time()

    res1 = list(_find_collection_dirs_to_purge(tree, now - 100))
    assert res1 == []

    res2 = list(_find_collection_dirs_to_purge(tree, now + 1))
    assert res2 == [tree[1]]


def test_purge_cache(tmpdir, tree, monkeypatch):
    now = time.time()
    monkeypatch.setattr(time, "time", lambda: now + 3600)
    purge_cache(7200, tmpdir.strpath)
    for x in tree:
        assert os.path.isdir(x), "directory has been deleted"

    purge_cache(1800, tmpdir.strpath)
    assert os.path.isdir(tree[0]), "empty directory has been deleted"
    assert not os.path.exists(tree[1]), "directory still there"
