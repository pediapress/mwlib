#! /usr/bin/env python

import heapq
import gevent
from gevent import event

class job(object):
    serial=None
    result=None
    error=None
    done=False
    
    def __init__(self, payload, priority=0, channel="default"):
        self.payload = payload
        self.priority = priority
        self.channel = channel
        self.metadata = {}
        
    def __cmp__(self, other):
        return cmp((self.priority, self.serial), (other.priority, other.serial))
        
class workq(object):
    def __init__(self):
        self.channel2q = {}
        self.merged = {}
        
        self.count = 0
        self._waiters = []
        self.id2job = {}
        

    def finishjob(self, jobid, result=None, error=None):
        j = self.id2job[jobid]
        j.result = result
        j.error = error
        j.done = True

    def updatejob(self, jobid, meta):
        j = self.id2job[jobid]
        j.metadata.update(meta)
        
    
                  
    def pushjob(self, job):
        if job.serial is None:
            self.count += 1
            job.serial = self.count

        self.id2job[job.serial] = job
        
        channel = job.channel
        
        for i, (watching, ev) in enumerate(self._waiters):
            if channel in watching or not watching:
                del self._waiters[i]
                ev.set(job)
                return job.serial

        try:
            q = self.channel2q[channel]
        except KeyError:
            q = self.channel2q[channel] = []
            
        heapq.heappush(q, job)
        return job.serial
        
    def push(self, payload, priority=0, channel="default"):
        return self.pushjob(job(payload, priority=priority, channel="default"))
        
    def pop(self, channels):
        if not channels:
            try_channels = self.channel2q.keys()
        else:
            try_channels = channels
            
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
