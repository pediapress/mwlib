#! /usr/bin/env python

import heapq
import random
import time
from functools import total_ordering

from gevent import event

from qs.log import root_logger

logger = root_logger.getChild("qserve.jobs")


@total_ordering
class job:
    serial = None
    jobid = None
    result = None
    error = None
    done = False
    deadline = None
    ttl = 3600
    drop = False

    def __init__(
        self, channel, payload=None, priority=0, jobid=None, timeout=None, ttl=None
    ):
        self.payload = payload
        self.priority = priority
        self.channel = channel
        self.info = {}
        self.jobid = jobid
        if timeout is None:
            timeout = 120.0
        self.timeout = time.time() + timeout
        self.finish_event = event.Event()

        if ttl is not None:
            self.ttl = ttl

    def __repr__(self):
        return f"<job {self.jobid!r} at {hex(id(self))}>"

    def __eq__(self, other):
        return (self.priority, self.serial) == (other.priority, other.serial)

    def __ne__(self, other):
        return not (self == other)

    def __le__(self, other):
        return (self.priority, self.serial) < (other.priority, other.serial)

    def __getstate__(self):
        d = self.__dict__.copy()
        del d["finish_event"]
        return d

    def __setstate__(self, state):
        self.__dict__ = state
        self.finish_event = event.Event()
        if self.done:
            self.finish_event.set()

    def _json(self):
        return self.__getstate__()


class workq:
    def __init__(self):
        self.channel2q = {}

        self.count = 0
        self._waiters = []
        self.id2job = {}
        self.timeoutq = []
        self._channel2count = {}

    def __getstate__(self):
        return {"count": self.count, "jobs": list(self.id2job.values())}

    def __setstate__(self, state):
        self.__init__()

        self.timeoutq = []
        self.count = state["count"]
        for j in state["jobs"]:
            self.id2job[j.jobid] = j
            if not j.done:
                self.timeoutq.append((j.timeout, j))
                channel = j.channel
                try:
                    q = self.channel2q[channel]
                except KeyError:
                    q = self.channel2q[channel] = []
                heapq.heappush(q, j)

        heapq.heapify(self.timeoutq)

    def _preenjobq(self, q):
        pop = heapq.heappop
        before = len(q)
        while q and q[0].done:
            pop(q)

        return before - len(q)

    def _preenall(self):
        for k, v in list(self.channel2q.items()):
            c = self._preenjobq(v)
            if c:
                logger.info(f"preen: {k} {c}")

    def _mark_finished(self, job, **kw):
        if job.done:
            return

        for k, v in list(kw.items()):
            setattr(job, k, v)
        job.done = True
        job.finish_event.set()

        try:
            c = self._channel2count[job.channel]
        except KeyError:
            c = self._channel2count[job.channel] = {
                "error": 0, "timeout": 0, "killed": 0, "success": 0
            }

        e = job.error
        if e is None:
            c["success"] += 1
        else:
            if e in ("timeout", "killed"):
                c[e] += 1
            elif e:
                c["error"] += 1

    def handletimeouts(self):
        now = time.time()
        while self.timeoutq:
            deadline, job = self.timeoutq[0]
            if job.done:
                heapq.heappop(self.timeoutq)
                continue
            if deadline > now:
                break

            heapq.heappop(self.timeoutq)
            self._mark_finished(job, error="timeout")
            logger.info(f"timeout: {job._json()}")

        self._preenall()

    def killjobs(self, jobids):
        for jid in jobids:
            if jid not in self.id2job:
                continue
            j = self.id2job[jid]
            if not j.done:
                self._mark_finished(j, error="killed")

    def dropjobs(self, jobids):
        "Mark jobs to be dropped when waitjobs() is called on them"

        for jid in jobids:
            if jid not in self.id2job:
                continue
            self.id2job[jid].drop = True

    def dropdead(self):
        "Drop jobs w/ expired deadline, add deadline to finished jobs w/out one"

        now = int(time.time())

        dcount = 0
        mcount = 0
        for jid, job in list(self.id2job.items()):
            if job.deadline and job.deadline < now:
                del self.id2job[jid]
                dcount += 1

            if job.done and not job.deadline:
                job.deadline = now + job.ttl
                mcount += 1
        if dcount or mcount:
            logger.info(
                f"watchdog: dropped {dcount} jobs, marked {mcount} jobs with a deadline"
            )

    def getstats(self):
        def count_not_done(lst):
            res = 0
            for x in lst:
                if not x.done:
                    res += 1
            return res

        stats = {
            "count": self.count,
            "numjobs": len(self.id2job),
            "channel2stat": self._channel2count,
            "busy": {
                c: count_not_done(todo) for c, todo in list(self.channel2q.items())
            },
        }
        return stats

    def report(self):
        status = ["processed: %s" % len(self.id2job), f"queued: {self.count}"]

        stats = self.getstats()
        busy = list(stats["busy"].items())
        busy.sort()

        if busy:
            details = ", ".join([f"{c}: {todo}" for c, todo in busy])
            status.append(f"busy channels: {details}")
        else:
            status.append("all channels idle")
        logger.info(" | ".join(status))

    def waitjobs(self, jobids):
        "Wait for jobs to finish. Drop jobs marked by dropjobs()."

        jobs = [self.id2job[jid] for jid in jobids]
        for j in jobs:
            j.finish_event.wait()
            if j.drop:
                del self.id2job[j.jobid]
        return jobs

    def finishjob(self, jobid, result=None, error=None):
        j = self.id2job[jobid]
        ttl = min(10, j.ttl) if error else j.ttl

        self._mark_finished(j, result=result, error=error, ttl=ttl)

    def updatejob(self, jobid, info):
        logger.info(f"updatejob {jobid} {info}")
        j = self.id2job[jobid]
        j.info.update(info)

    def pushjob(self, job):
        if job.serial is None:
            self.count += 1
            job.serial = self.count

        if job.jobid is None:
            job.jobid = job.serial
        self.id2job[job.jobid] = job

        channel = job.channel

        alternatives = []
        for watching, ev in self._waiters:
            if channel in watching or not watching:
                alternatives.append(ev)

        heapq.heappush(self.timeoutq, (job.timeout, job))

        if alternatives:
            random.choice(alternatives).set(job)
            return job.jobid

        try:
            q = self.channel2q[channel]
        except KeyError:
            q = self.channel2q[channel] = []

        heapq.heappush(q, job)

        return job.jobid

    def push(
        self, channel, payload=None, priority=0, jobid=None, timeout=None, ttl=None
    ):
        if jobid is not None and jobid in self.id2job and self.id2job[jobid].error != "killed":
            return jobid
        logger.info(f"Job {jobid} not found, pushing new job")
        return self.pushjob(
            job(
                payload=payload,
                priority=priority,
                channel=channel,
                jobid=jobid,
                timeout=timeout,
                ttl=ttl,
            )
        )

    def pop(self, channels):
        try_channels = channels if channels else list(self.channel2q.keys())

        self._preenall()

        jobs = []
        for c in try_channels:
            try:
                q = self.channel2q[c]
            except KeyError:
                continue
            if q:
                jobs.append(q[0])

        if jobs:
            j = min(jobs)
            heapq.heappop(self.channel2q[j.channel])
        else:
            ev = event.AsyncResult()
            self._waiters.append((channels, ev))
            try:
                j = ev.get()
            finally:
                self._waiters.remove((channels, ev))

        return j

    def prefixmatch(self, prefix):
        for jobid in self.id2job:
            if isinstance(jobid, str) and jobid.startswith(prefix):
                yield jobid
