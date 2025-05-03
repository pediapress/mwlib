#! /usr/bin/env py.test

import io
import pickle
import sys
import time
from builtins import chr, object, range

import pytest
from gevent import pool, sleep

from qs import jobs


@pytest.fixture
def wq(request):
    return jobs.workq()


@pytest.fixture
def spawn(request):
    p = pool.Pool()
    request.addfinalizer(p.kill)
    return p.spawn


@pytest.fixture
def faketime(request):
    monkeypatch = request.getfixturevalue("monkeypatch")

    class faketime:
        def __init__(self):
            self.current_time = time.time()

        def __call__(self):
            return self.current_time

        def __iadd__(self, value):
            self.current_time += value
            return self

        def __repr__(self):
            return "<faketime %s>" % self.current_time

    ft = faketime()
    monkeypatch.setattr(time, "time", ft)
    return ft


def loaddump(obj):
    return pickle.loads(pickle.dumps(obj))


# -- tests
def test_job_defaults():
    now = time.time()
    j1 = jobs.job("render")
    assert j1.ttl == 3600
    assert j1.priority == 0
    assert j1.timeout >= now + 120


def test_job_repr_unicode():
    r = repr(jobs.job("render", jobid=chr(256)))
    assert isinstance(r, str)


def test_job_repr_none():
    assert "<job None at" in repr(jobs.job("render"))


def test_job_repr_int():
    assert repr(jobs.job("render", jobid=41))[6].isdigit()


def test_job_pickle():
    j1 = jobs.job("render", payload=(1, 2, 3), priority=5, jobid=11, timeout=100, ttl=20)
    j2 = loaddump(j1)

    assert j2.channel == "render"
    assert j2.payload == (1, 2, 3)
    assert j2.priority == 5
    assert j2.jobid == 11
    assert j2.timeout == j1.timeout
    assert j2.ttl == 20
    assert j2.done is False


def test_job_unpickle_event():
    j = jobs.job("render")
    j = loaddump(j)
    assert not j.finish_event.is_set()

    j.done = True
    j = loaddump(j)
    assert j.finish_event.is_set()


def test_job_json():
    jobs.job("render", jobid=chr(256))._json()


def test_workq_pickle(wq):
    wq.pushjob(jobs.job("render1"))
    wq.pushjob(jobs.job("render2"))
    w2 = loaddump(wq)
    print(wq.__dict__)
    print(w2.__dict__)
    assert wq.__dict__ == w2.__dict__


def test_pushjob_automatic_jobid(wq):
    for x in range(1, 10):
        j = jobs.job("render", payload="hello")
        jid = wq.pushjob(j)
        assert (jid, j.jobid) == (x, x)


def test_pushjob_no_automatic_jobid(wq):
    for jobid in ["", "123", chr(255), 0]:
        j = jobs.job("render", payload="hello", jobid=jobid)
        jid = wq.pushjob(j)
        assert (jid, j.jobid) == (jobid, jobid)


def test_pushjob_pop(wq, spawn):
    j1 = jobs.job("render", payload="hello")
    jid = wq.pushjob(j1)
    assert jid == 1
    assert j1.jobid == 1
    assert len(wq.channel2q["render"]) == 1
    assert len(wq.timeoutq) == 1

    j = wq.pop(["foo", "render", "bar"])
    assert j is j1

    g1 = spawn(wq.pop, ["render"])
    sleep(0)

    j2 = jobs.job("render", payload=" world")
    wq.pushjob(j2)
    g1.join()
    res = g1.get()
    assert res is j2


def test_stats(wq):
    joblst = [wq.push("render", payload=i) for i in range(10)]
    stats = wq.getstats()
    print("stats before", stats)
    assert stats == {"count": 10, "busy": {"render": 10}, "channel2stat": {}, "numjobs": 10}

    wq.killjobs(joblst[1:])

    stats = wq.getstats()
    print("stats after", stats)
    assert stats == {
        "count": 10,
        "busy": {"render": 1},
        "channel2stat": {"render": {"success": 0, "killed": 9, "timeout": 0, "error": 0}},
        "numjobs": 10,
    }
    print(wq.waitjobs(joblst[1:]))


def test_report(wq, caplog):
    wq.report()
    assert "all channels idle" in caplog.text

    joblst = [wq.push("render", payload=i) for i in range(10)]
    wq.killjobs(joblst[2:])
    wq.report()
    assert "render: 10" not in caplog.text
    assert "render: 2" in caplog.text


def test_killjobs_unknown_jobid(wq):
    wq.killjobs([1, 2, 3])


def test_pop_does_preen(wq):
    jlist = [jobs.job("render", payload=i) for i in range(10)]
    for j in jlist:
        wq.pushjob(j)

    for j in jlist[:-1]:
        wq._mark_finished(j, killed=True)

    print(wq.__dict__)
    j = wq.pop(["render"])
    print(j, jlist)
    assert j is jlist[-1]


def test_pop_new_channel(wq, spawn):
    wq.push("foo")
    wq.pop([])  # wq.channel2q == {'foo': []} now
    print(wq.__dict__)

    gr = spawn(wq.pop, [])
    sleep(0)

    jid = wq.push("render")
    res = gr.get(timeout=0.2)
    assert res.jobid == jid


def test_updatejob(wq):
    j = jobs.job("render")
    wq.pushjob(j)
    jid = j.jobid
    assert j.info == dict()

    wq.updatejob(jid, dict(bar=5))
    assert j.info == dict(bar=5)

    wq.updatejob(jid, dict(foo=7))
    assert j.info == dict(foo=7, bar=5)


def test_handletimeouts_empty(wq):
    wq.handletimeouts()


def test_handletimeouts(wq, faketime):
    j1 = jobs.job("render", timeout=10)
    j2 = jobs.job("render", timeout=9)

    wq.pushjob(j1)
    wq.pushjob(j2)
    assert wq.timeoutq[0][1] is j2

    faketime += 9.5
    wq.handletimeouts()

    assert not j1.done
    assert j2.done
    assert j2.error == "timeout"


def test_handletimeouts_with_client_waiting(wq, faketime, spawn):
    spawn(wq.pop, ["render"])
    sleep(0.0)
    j = jobs.job("render", timeout=9.5)
    wq.pushjob(j)
    assert len(wq.timeoutq) == 1
    assert wq.timeoutq[0][1] is j

    faketime += 10
    wq.handletimeouts()

    assert j.done
    assert j.error == "timeout"


def test_handletimeouts_unless_done(wq, faketime):
    j1 = jobs.job("render", timeout=10)
    j2 = jobs.job("render", timeout=9)

    wq.pushjob(j1)
    wq.pushjob(j2)

    wq._mark_finished(j2)
    faketime += 11
    wq.handletimeouts()
    assert not wq.timeoutq

    assert j1.error == "timeout"
    assert j2.error is None


def test_mark_finished(wq):
    def mark_finished(**kw):
        j = jobs.job("render")
        wq.pushjob(j)
        wq._mark_finished(j, **kw)
        return j

    j = mark_finished(error="not found")
    assert j.done
    assert j.error == "not found"
    assert wq._channel2count["render"] == dict(error=1, timeout=0, killed=0, success=0)

    wq._mark_finished(j, error="no")
    assert j.error == "not found"
    assert wq._channel2count["render"] == dict(error=1, timeout=0, killed=0, success=0)

    mark_finished(error="killed")
    assert wq._channel2count["render"] == dict(error=1, timeout=0, killed=1, success=0)

    mark_finished()
    assert wq._channel2count["render"] == dict(error=1, timeout=0, killed=1, success=1)

    mark_finished(error="timeout")
    assert wq._channel2count["render"] == dict(error=1, timeout=1, killed=1, success=1)


def test_pop_cleanup_waiters_if_killed(wq, spawn):
    gr = spawn(wq.pop, [])
    sleep(0.0)
    print("before", wq.__dict__)
    assert len(wq._waiters) == 1
    gr.kill()
    print("after", wq.__dict__)
    assert len(wq._waiters) == 0
