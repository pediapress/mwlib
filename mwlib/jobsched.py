"""Simplistic threaded job scheduler"""

import Queue
import threading
import traceback

from mwlib.log import Log

log = Log('mwlib.jobsched')

# ==============================================================================

class JobScheduler(object):
    """Simple threaded job scheduler"""
    
    def __init__(self, num_threads, do_job):
        """Init instance with a number of worker threads and a job callable
        
        @param num_threads: number of threads to start
        @type num_threads: int
        
        @param do_job: callable which gets called with a job ID and job-specific
            kwargs, which returns some job-specific result, and which performs a
            job in a separate thread
        @type do_job: callable with signature do_job(job_id, **kwargs) -> object
        """
        
        self.num_threads = num_threads
        self.do_job = do_job
        self.job_queue = Queue.Queue()
        self.results = {}
        self.results_lock = threading.RLock()
        self.started = False
    
    def add_job(self, job_id, **kwargs):
        """Schedule a job to be executed in a separate thread. The job_id and
        all additional kwargs are passed to the do_job callable given in the
        constructor.
        
        If called for the first time on this instance, the worker threads will
        be started by this method.
        
        @param job_id: unique ID for this job
        @type job_id: hashable object
        """
        
        def worker():
            try:
                while True:
                    job_id, kwargs = self.job_queue.get()
                    try:
                        if job_id == 'die':
                            break
                        try:                
                            result = self.do_job(job_id, **kwargs)
                        except Exception, exc:
                            log.ERROR('Error executing job: %s' % exc)
                            traceback.print_exc()
                        self.results_lock.acquire()
                        self.results[job_id] = result
                        self.results_lock.release()
                    finally:
                        self.job_queue.task_done()
            except:
                traceback.print_exc()
        
        if not self.started:
            self.started = True
            for i in range(self.num_threads):
                thread = threading.Thread(target=worker)
                thread.setDaemon(True)
                thread.start()
        
        self.job_queue.put((job_id, kwargs))
    
    def get_results(self):
        """Wait for all queued jobs to be finished and return results dictionary
        mapping job IDs to the results returned by the do_job callable.
        
        After this method returns, all threads of this scheduler are killed.
        
        @returns: dictionary containing results
        @rtype: dict
        """
        
        if self.started:
            for i in range(self.num_threads):
                self.job_queue.put(('die', None))
            self.job_queue.join()
            self.started = False
        return self.results
    

