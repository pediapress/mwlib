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
        return m(**kwargs)
    
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
    
        
        
        
    
def main(commands, host="localhost", port=None, numthreads=10):
    if port is None:
        port = 14311
    class workhandler(worker, commands):
        pass

    channels=[]
    for x in dir(workhandler):
        if x.startswith("rpc_"):
            channels.append(x[len("rpc_"):])
    channels.sort()

    assert channels, "no channels"
    
    def start_worker():
        qs = serverproxy(host=host, port=port)
                
        sleeptime = 0.5
        
        while 1:
            try:
                job = qs.qpull(channels=channels)
            except Exception, err:
                print "Error while calling pulljob:", str(err)
                time.sleep(sleeptime)
                if sleeptime<60:
                    sleeptime*=2
                continue

            sleeptime = 0.5
            

            print "got job:", job
            try:
                result = workhandler(qs).dispatch(job)
            except Exception, err:
                print "error:", err
                try:
                    qs.qfinish(jobid=job["jobid"], error=shorterrmsg())
                    traceback.print_exc()
                except:
                    pass
                continue

            try:
                qs.qfinish(jobid=job["jobid"], result=result)
            except:
                pass

    print "pulling jobs from", "%s:%s" % (host, port), "for", ", ".join(channels)
    
    import threading
    for i in range(numthreads):
        t=threading.Thread(target=start_worker)
        t.start()
    
    try:
        while True:
            time.sleep(2**26)
    finally:
        os._exit(0)
