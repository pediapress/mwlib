#! /usr/bin/env py.test

import pytest, gevent, nserve, urllib, urllib2, bottle
import wsgi_intercept.urllib2_intercept

try:
    import json
except ImportError:
    import simplejson as json


def post(**kw):
    try:
        r = urllib2.urlopen('http://app.de/', urllib.urlencode(kw))
        data = r.read()
        data = json.loads(data)
        return (r.code, data)
    except urllib2.HTTPError, e:
        return (e.code, e.read())


def get_exception_raiser(msg, exception_class=RuntimeError):
    def raise_exc(*args, **kwargs):
        raise exception_class(msg)
    return raise_exc

raise_greenletexit = get_exception_raiser("killed", gevent.GreenletExit)


def pytest_funcarg__app(request):
    wsgi_intercept.urllib2_intercept.install_opener()
    request.addfinalizer(wsgi_intercept.urllib2_intercept.uninstall_opener)
    wsgi_intercept.add_wsgi_intercept('app.de', 80, bottle.default_app)
    request.addfinalizer(lambda: wsgi_intercept.remove_wsgi_intercept("app.de", 80))
    return None


def pytest_funcarg__busy(request):
    busy = {}
    monkeypatch = request.getfuncargvalue("monkeypatch")
    monkeypatch.setattr(nserve, "busy", busy)
    return busy


def pytest_funcarg__wq(request):
    busy = request.getfuncargvalue("busy")
    wq = nserve.watch_qserve(("localhost", 8888), busy)
    wq.getstats_timeout = 0.01
    wq.sleep_time = 0.01
    busy[wq.ident] = True
    return wq


# -- tests

def test_make_collection_id_version(monkeypatch):
    data = {}
    id1 = nserve.make_collection_id(data)
    from mwlib import _version
    monkeypatch.setattr(_version, "version", (0, 1, 0))
    id2 = nserve.make_collection_id(data)
    assert id1 != id2


def test_check_collection_id():
    cc = nserve.Application().check_collection_id
    assert not cc("a" * 15)
    assert not cc("a" * 17)
    assert cc("a" * 16)
    assert not cc("A" * 16)
    assert cc("0123456789abcdef")
    assert not cc("g" * 16)


def test_choose_idle_qserve(monkeypatch, busy):
    assert nserve.choose_idle_qserve() is None
    busy["host1"] = True
    assert nserve.choose_idle_qserve() is None
    busy["host2"] = False
    assert nserve.choose_idle_qserve() == "host2"
    busy["host1"] = False
    assert set(nserve.choose_idle_qserve() for i in range(20)) == set(["host1", "host2"])


def test_watch_qserve_iterate_overloaded(busy, wq):
    wq._getstats = lambda *args: dict(busy=dict(render=11))
    wq._iterate()
    assert busy[wq.ident] == "system overloaded"


def test_watch_qserve_iterate_down(busy, wq):
    wq._getstats = get_exception_raiser("getstats failed")
    wq._iterate()
    assert busy[wq.ident] == "system down"


def test_watch_qserve_iterate_killable(busy, wq):
    wq._getstats = raise_greenletexit
    pytest.raises(gevent.GreenletExit, wq._iterate)


def test_watch_qserve_call_killable(wq):
    wq._getstats = raise_greenletexit
    wq._sleep = get_exception_raiser("do not call sleep")
    pytest.raises(gevent.GreenletExit, wq)


def test_app_no_command(app):
    code, data = post()
    assert (code, data) == (400, "no command given")


def test_app_unknown_command(app):
    code, data = post(command="gohome")
    assert code == 400
    assert "no such command" in data


def test_app_do_render_overloaded(app):
    code, data = post(command="render")
    print code, data

    assert code == 200
    assert "overloaded" in data["error"]


def test_app_do_render_missing_metabook(app, busy):
    busy[("host1", 8000)] = False

    code, data = post(command="render", writer="odf")
    print code, data

    assert code == 200
    assert "metabook or collection_id required" in data["error"]


def test_app_dispatch_bad_collid(app, busy):
    code, data = post(command="render", collection_id="a" * 15)
    print code, data
    assert code == 404
