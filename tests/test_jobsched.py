#! /usr/bin/env py.test

import time

from mwlib.jobsched import JobScheduler

def test_jobsched():
    results = {}
    
    def wait(job_id, wait_time=None):
        print 'start', job_id
        time.sleep(wait_time)
        print 'finish', job_id
        results[job_id] = wait_time
    
    sched = JobScheduler(5)
    for i in range(2): # test reusability
        n = 10
        for i in range(n):
            sched.add_job(i, wait, wait_time=0.01*i)
        s = time.time()
        sched.join()
        t = time.time() - s
        print 'join() took %f secs' % t
        assert t >= 0.01
        print results
        for i in range(n):
            assert results[i] == 0.01*i
        results.clear()

def test_empty():
    sched = JobScheduler(5)
    sched.join()
