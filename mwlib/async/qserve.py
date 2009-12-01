#! /usr/bin/env python
import os
import cPickle
import getopt # yes, getopt!
import sys

from mwlib.async import jobs
    
class db(object):
    def __init__(self):
        self.key2data = {}
        self.workq = jobs.workq()
        
class qplugin(object):
    def __init__(self,  **kw):
        self.running_jobs = {}
        
    def rpc_qadd(self, channel, payload=None, priority=0, jobid=None, wait=False, timeout=None, ttl=None):
        jobid = self.workq.push(payload=payload, priority=priority, channel=channel, jobid=jobid, timeout=timeout, ttl=ttl)
        if not wait:
            return jobid
        
        res = self.workq.waitjobs([jobid])[0]
        return res._json()
    
    def rpc_qpull(self, channels=None):
        if not channels:
            channels = []
            
        j = self.workq.pop(channels)
        self.running_jobs[j.jobid] = j
        
        return j._json()

    def rpc_qfinish(self, jobid, result=None, error=None, traceback=None):
        if error:
            print "error finish: %s: %r" % (jobid, error)
        else:
            print "finish: %s: %r" % (jobid, result)
        self.workq.finishjob(jobid, result=result, error=error)
        if jobid in self.running_jobs:
            del self.running_jobs[jobid]
        
    def rpc_qsetinfo(self, jobid, info):
        self.workq.updatejob(jobid, info)

    def rpc_qinfo(self, jobid):
        if jobid in self.workq.id2job:
            return self.workq.id2job[jobid]._json()
        return None

    def rpc_qwait(self, jobids):
        res = self.workq.waitjobs(jobids)
        return [j._json() for j in res]

    def rpc_qkill(self, jobids):
        self.workq.killjobs(jobids)
        
        for jobid in jobids:
            if jobid in self.running_jobs:
                del self.running_jobs[jobid]
        
    
    def shutdown(self):
        for j in self.running_jobs.values():
            # print "reschedule", j
            self.workq.pushjob(j)
        
def usage():
    print "mw-qserve [-p PORT] [-i INTERFACE] [-d DATADIR]"

def main():
    from mwlib.async.rpcserver import request_handler, server

    try:
        opts, args = getopt.getopt(sys.argv[1:], "d:p:i:h", ["help", "port=", "interface="])
    except getopt.GetoptError, err:
        print str(err)
        sys.exit(10)

    port = 14311
    interface = "0.0.0.0"
    datadir = None
    
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
        elif o in ("-d"):
            datadir = a
        elif o in ("-h", "--help"):
            usage()
            sys.exit(0)

    if datadir is not None:
        if not os.path.isdir(datadir):
            sys.exit("%r is not a directory" % (datadir, ))
        qpath = os.path.join(datadir, "workq.pickle")
    else:
        qpath = None
        
    if qpath and os.path.exists(qpath):
        print "loading", qpath
        d = cPickle.load(open(qpath))
        print "loaded", len(d.workq.id2job), "jobs"
    else:
        d = db()

    def handletimeouts():
        while 1:
            d.workq.handletimeouts()
            gevent.sleep(1)
            
    def watchdog():
        while 1:
            d.workq.dropdead()
            gevent.sleep(30)
            
    def report():
        while 1:
            d.workq.report()
            gevent.sleep(20)
        
    import gevent
    gevent.spawn(report)
    gevent.spawn(watchdog)
    gevent.spawn(handletimeouts)
    
    class handler(request_handler, qplugin):
        def __init__(self, **kwargs):
            super(handler, self).__init__(**kwargs)
            
        workq = d.workq
        db = d

    s=server(port, host=interface, get_request_handler=handler)
    print "listening on %s:%s" % (interface, port)
    try:
        s.run_forever()
    except KeyboardInterrupt:
        print "interrupted"
    finally:
        if qpath:
            print "saving", qpath
            cPickle.dump(d, open(qpath, "w"), 2)
        
    
if __name__=="__main__":
    main()
