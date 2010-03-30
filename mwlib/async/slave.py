#! /usr/bin/env python

import sys
import os
import time
import traceback

from mwlib.async.rpcclient import serverproxy

def shorterrmsg():
    etype, val, tb = sys.exc_info()
    msg = []
    a = msg.append
    
    a(etype.__name__)
    a(": ")
    a(str(val))
    
    file, lineno, name, line = traceback.extract_tb(tb)[-1]
    a(" in function %s, file %s, line %s" % (name, file,  lineno))
    
    return "".join(msg)

class worker(object):
    def __init__(self, proxy):
        self.proxy = proxy

    def dispatch(self, job):
        self.job = job
        self.jobid = job["jobid"]
        self.priority = job["priority"]
        self.jobid_prefix = None
                    
        method = job["channel"]
        
        m=getattr(self, "rpc_"+method, None)
        if m is None:
            raise RuntimeError("no such method %r" % (method, ))
        
        kwargs = job.get("payload") or dict()
        tmp = {}
        for k, v in kwargs.items():
            if isinstance(k, unicode):
                tmp[str(k)] = v
            else:
                tmp[k] = v
                
        return m(**tmp)
    
    def qsetinfo(self, info):
        return self.proxy.qsetinfo(jobid=self.jobid, info=info)

    def qadd(self, channel, payload=None, jobid=None, prefix=None, wait=False, timeout=None, ttl=None):
        """call qadd on proxy with the same priority as the current job"""
        if jobid is None and prefix is not None:
            jobid = "%s::%s" % (prefix, channel)
            
        return self.proxy.qadd(channel=channel, payload=payload, priority=self.priority, jobid=jobid, wait=wait, timeout=timeout, ttl=ttl)

    def qaddw(self, channel, payload=None, jobid=None, timeout=None):
        r = self.proxy.qadd(channel=channel, payload=payload, priority=self.priority, jobid=jobid, wait=True, timeout=timeout)
        error = r.get("error")
        if error is not None:
            raise RuntimeError(error)
        
        return r["result"]
    
        
        
        
    
def main(commands, host="localhost", port=None, numthreads=10, numprocs=0, numgreenlets=0, argv=None):
    if port is None:
        port = 14311
        
    channels = []
    skip_channels = []
    
    if argv:
        import getopt
        
        try:
            opts, args = getopt.getopt(argv, "c:s:", ["host=", "port=", "numthreads=", "numprocs=", "channel=",  "skip="])
        except getopt.GetoptError, err:
            print str(err)
            sys.exit(10)
            
        for o, a in opts:
            if o=="--host":
                host = a
            if o=="--port":
                port = int(a)
            if o=="--numthreads":
                numthreads=int(a)
                numprocs=0
            if o=="--numprocs":
                numprocs=int(a)
                numthreads=0
            if o=="-c" or o=="--channel":
                channels.append(a)
            if o=="-s" or o=="--skip":
                skip_channels.append(a)
                
            
            
    class workhandler(worker, commands):
        pass

    available_channels=[]
    for x in dir(workhandler):
        if x.startswith("rpc_"):
            available_channels.append(x[len("rpc_"):])
    available_channels.sort()
    
    if not channels:
        channels = available_channels
    else:
        for c in channels:
            assert c in available_channels, "no such channel: %s" % c

    for c in skip_channels:
        channels.remove(c)
        
    
            
    assert channels, "no channels"

    if numprocs:
        def checkparent():
            if os.getppid()==1:
                print "parent died. exiting."
                os._exit(0)
    else:
        def checkparent():
            pass
        

    def handle_one_job(qs):
        sleeptime = 0.5
        
        while 1:
            try:
                job = qs.qpull(channels=channels)
                break
            except Exception, err:
                checkparent()
                print "Error while calling pulljob:", str(err)
                time.sleep(sleeptime)
                checkparent()
                if sleeptime<60:
                    sleeptime*=2

        checkparent()            
        # print "got job:", job
        try:
            result = workhandler(qs).dispatch(job)
        except Exception, err:
            print "error:", err
            try:
                qs.qfinish(jobid=job["jobid"], error=shorterrmsg())
                traceback.print_exc()
            except:
                pass
            return

        try:
            qs.qfinish(jobid=job["jobid"], result=result)
        except:
            pass
        
    
    
    def start_worker():
        qs = serverproxy(host=host, port=port)
        while 1:
            handle_one_job(qs)
            
    print "pulling jobs from", "%s:%s" % (host, port), "for", ", ".join(channels)

    def run_with_threads():
        import threading
        for i in range(numthreads):
            t=threading.Thread(target=start_worker)
            t.start()

        try:
            while True:
                time.sleep(2**26)
        finally:
            os._exit(0)

    def run_with_procs():
        children = set()

        while 1:
            while len(children)<numprocs:
                try:
                    pid = os.fork()
                except:
                    print "failed to fork child"
                    time.sleep(1)
                    continue
                
                if pid==0:
                    try:
                        qs = serverproxy(host=host, port=port)
                        handle_one_job(qs)
                    finally:
                        os._exit(0)
                # print "forked", pid
                children.add(pid)
                
            try:    
                pid, st = os.waitpid(-1, 0)
            except OSError:
                continue

            # print "done",  pid
            try:
                children.remove(pid)
            except KeyError:
                pass

    def run_with_gevent():
        import gevent
        for i in range(numgreenlets):
            gevent.spawn(start_worker)
            
        try:
            while True:
                time.sleep(2**26)
        finally:
            os._exit(0)
            
    if numgreenlets>0:
        run_with_gevent()
    elif numprocs>0:
        run_with_procs()
    elif numthreads>0:
        run_with_threads()
    else:
        assert 0, "bad"
    
        

    
if __name__=="__main__":
    class commands:
        def rpc_divide(self, a, b):
            print "rpc_divide", (a,b)
            return a / b
        
    main(commands, numprocs=2)
