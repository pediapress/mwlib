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
    
    class handler(request_handler, qplugin):
        workq = d.workq
        db = d

    s=server(port, host=interface, get_request_handler=handler)
    print "listening on %s:%s" % (interface, port)
    s.run_forever()
    
if __name__=="__main__":
    main()
