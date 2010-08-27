#! /usr/bin/env python
import random
import heapq
import time
import gevent
from gevent import event

class job(object):
    serial = None
    jobid=None
    result=None
    error=None
    done=False
    deadline = None
    ttl = 3600
    drop = False
    
    def __init__(self, channel, payload=None, priority=0, jobid=None, timeout=120, ttl=None):
        self.payload = payload
        self.priority = priority
        self.channel = channel
        self.info = {}
        self.jobid = jobid
        self.timeout = time.time()+timeout
        self.finish_event = event.Event()
        
        if ttl is not None:
            self.ttl = ttl
            
    def __cmp__(self, other):
        return cmp((self.priority, self.serial), (other.priority, other.serial))

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
        d = self.__dict__.copy()
        del d["finish_event"]
        return d
    
class workq(object):
    def __init__(self):
        self.channel2q = {}
        
        self.count = 0
        self._waiters = []
        self.id2job = {}
        self.timeoutq = []
        self._channel2count = {}

    def __getstate__(self):
        return dict(count=self.count, jobs=self.id2job.values())

    def __setstate__(self, state):
        self.__init__()
        
        self.timeoutq = []
        self.count = state["count"]
        for j in state["jobs"]:
            self.id2job[j.jobid] = j
            if not j.done:
                self.timeoutq.append((j.timeout, j))
        heapq.heapify(self.timeoutq)
        
    def _preenjobq(self, q):
        pop = heapq.heappop
        before = len(q)
        while q and q[0].done:
            pop(q)
            
        return before-len(q)
    
    def _preenall(self):
        for k, v in self.channel2q.items():
            c = self._preenjobq(v)
            if c:
                print "preen:", k,c

    def _mark_finished(self, job, **kw):
        if job.done:
            return

        for k, v in kw.items():
            setattr(job, k, v)
        job.done = True
        job.finish_event.set()

        try:
            c = self._channel2count[job.channel]
        except KeyError:
            c = self._channel2count[job.channel] = dict(error=0, timeout=0, killed=0, success=0)

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
            print "timeout:", job._json()

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
        for jid, job in self.id2job.items():
            if job.deadline and job.deadline < now:
                del self.id2job[jid]
                dcount += 1

            if job.done and not job.deadline:
                job.deadline = now+job.ttl
                mcount += 1
        if dcount or mcount:
            print "watchdog: dropped %s jobs, marked %s jobs with a deadline" % (dcount, mcount)
        
    def getstats(self):
        stats = dict(count=self.count,
                     numjobs=len(self.id2job),
                     channel2stat = self._channel2count,
                     busy = dict([(c, len(todo)) for c, todo in self.channel2q.items()]))
        return stats

    def report(self):
        print "=== report %s ===" % (time.ctime(), )
        print "have %s jobs" % len(self.id2job)
        print "count:", self.count
        busy = []
        for c, todo in self.channel2q.items():
            if todo:
                busy.append((c, len(todo)))
        if busy:
            print "busy channels:"
            todo.sort()
            for c, todo in busy:
                print c, todo
        else:
            print "all channels idle"
            
        print
        
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
        if error:
            ttl = min(10, j.ttl)
        else:
            ttl = j.ttl

        self._mark_finished(j, result=result, error=error, ttl=ttl)

    def updatejob(self, jobid, info):
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
        for i, (watching, ev) in enumerate(self._waiters):
            if channel in watching or not watching:
                alternatives.append((i,ev))

        if alternatives:
            i, ev = random.choice(alternatives)
            del self._waiters[i]
            ev.set(job)
            return job.jobid

        try:
            q = self.channel2q[channel]
        except KeyError:
            q = self.channel2q[channel] = []
            
        heapq.heappush(q, job)
        heapq.heappush(self.timeoutq, (job.timeout, job))
        
        return job.jobid


    def push(self, channel, payload=None, priority=0, jobid=None, timeout=None, ttl=None):
        if jobid is not None:
            if jobid in self.id2job and self.id2job[jobid].error!="killed":
                return jobid
            
        if timeout is None:
            timeout=120
            
        
        return self.pushjob(job(payload=payload, priority=priority, channel=channel, jobid=jobid, timeout=timeout, ttl=ttl))
        
    def pop(self, channels):
        if not channels:
            try_channels = self.channel2q.keys()
        else:
            try_channels = channels

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
            j = ev.get()
            
        return j

    def prefixmatch(self, prefix):
        for jobid in self.id2job:
            if isinstance(jobid, basestring) and jobid.startswith(prefix):
                yield jobid
