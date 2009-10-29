#! /usr/bin/env python

from mwlib.async import jobs
    
class db(object):
    def __init__(self):
        self.key2data = {}
        self.workq = jobs.workq()
        
class qplugin:
    running_jobs = None
    
    def rpc_addjob(self, payload, priority=0, channel="default"):
        return self.workq.push(payload, priority=priority, channel=channel)

    def rpc_pulljob(self, channels=None):
        if not channels:
            channels = []

        if self.running_jobs is None:
            self.running_jobs = {}
            
        j = self.workq.pop(channels)
        self.running_jobs[j.serial] = j
        
        return j.__dict__

    def rpc_finishjob(self, jobid, result=None, error=None):
        self.workq.finishjob(jobid, result=result, error=error)

    def rpc_updatejob(self, jobid, data):
        self.workq.updatejob(jobid, data)
        
    def shutdown(self):
        if not self.running_jobs:
            return
        
        for j in self.running_jobs.values():
            # print "reschedule", j
            self.workq.pushjob(j)
            
        self.running_jobs = None
        
        
        
    
def main():
    from mwlib.async.rpcserver import request_handler, server

    d = db()
    
    class handler(request_handler, qplugin):
        workq = d.workq
        db = d
        
    server(8080, get_request_handler=handler).run_forever()
        
if __name__=="__main__":
    main()
