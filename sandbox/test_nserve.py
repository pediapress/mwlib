#! /usr/bin/env py.test

import nserve


def pytest_funcarg__app(request):
    tmpdir = request.getfuncargvalue("tmpdir")
    app = nserve.Application(tmpdir.strpath)
    return app


# -- tests

def test_make_collection_id_version(monkeypatch):
    data = {}
    id1 = nserve.make_collection_id(data)
    from mwlib import _version
    monkeypatch.setattr(_version, "version", (0, 1, 0))
    id2 = nserve.make_collection_id(data)
    assert id1 != id2


def test_check_collection_id(app):
    cc = app.check_collection_id
    assert not cc("a" * 15)
    assert not cc("a" * 17)
    assert cc("a" * 16)
    assert not cc("A" * 16)
    assert cc("0123456789abcdef")
    assert not cc("g" * 16)


def test_choose_idle_qserve(monkeypatch):
    busy = {}
    monkeypatch.setattr(nserve, "busy", busy)
    assert nserve.choose_idle_qserve() is None
    busy["host1"] = True
    assert nserve.choose_idle_qserve() is None
    busy["host2"] = False
    assert nserve.choose_idle_qserve() == "host2"
    busy["host1"] = False
    assert set(nserve.choose_idle_qserve() for i in range(20)) == set(["host1", "host2"])
