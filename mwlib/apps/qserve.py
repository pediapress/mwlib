#! /usr/bin/env python

import getopt # yes, getopt!
import sys

from mwlib.async import jobs
    
class db(object):
    def __init__(self):
        self.key2data = {}
        self.workq = jobs.workq()
        
class qplugin:
    running_jobs = None
    
    def rpc_addjob(self, payload, priority=0, channel="default", jobid=None):
        return self.workq.push(payload, priority=priority, channel=channel, jobid=jobid)

    def rpc_pulljob(self, channels=None):
        if not channels:
            channels = []

        if self.running_jobs is None:
            self.running_jobs = {}
            
        j = self.workq.pop(channels)
        self.running_jobs[j.jobid] = j
        
        return j._json()

    def rpc_finishjob(self, jobid, result=None, error=None, traceback=None):
        if error:
            print "error finish: %s: %r" % (jobid, error)
        else:
            print "finish: %s: %r" % (jobid, result)
        self.workq.finishjob(jobid, result=result, error=error)
        if self.running_jobs and jobid in self.running_jobs:
            del self.running_jobs[jobid]
        
    def rpc_updatejob(self, jobid, progress):
        self.workq.updatejob(jobid, progress)

    def rpc_jobinfo(self, jobid):
        if jobid in self.workq.id2job:
            return self.workq.id2job[jobid]._json()
        return None

    def rpc_waitjobs(self, jobids):
        res = self.workq.waitjobs(jobids)
        return [j._json() for j in res]
    
    def shutdown(self):
        if not self.running_jobs:
            return
        
        for j in self.running_jobs.values():
            # print "reschedule", j
            self.workq.pushjob(j)
            
        self.running_jobs = None
        
        
        
def usage():
    print "mw-qserve [-p PORT] [-i INTERFACE]"

def main():
    from mwlib.async.rpcserver import request_handler, server

    try:
        opts, args = getopt.getopt(sys.argv[1:], "p:i:h", ["port", "interface"])
    except getopt.GetoptError, err:
        print str(err)
        sys.exit(10)

    port = 14311
    interface = "0.0.0.0"
    
    for o, a in opts:
        if o in ("-p", "--port"):
            try:
                port = int(a)
                if port<=0 or port>65535:
                    raise ValueError("bad port")
            except ValueError:
                print "expected positive integer as argument to %s" % o
                sys.exit(10)
        elif o in ("-i",  "--interface"):
            interface = a
        elif o in ("-h", "--help"):
            usage()
            sys.exit(0)
                                  
    
    d = db()

    def report():
        while 1:
            d.workq.report()
            gevent.sleep(20)
        
    import gevent
    gevent.spawn(report)
    
    
    class handler(request_handler, qplugin):
        workq = d.workq
        db = d

    s=server(port, host=interface, get_request_handler=handler)
    print "listening on %s:%s" % (interface, port)
    s.run_forever()
    
if __name__=="__main__":
    main()
