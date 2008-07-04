import atexit
import Queue
import threading
import traceback

from mwlib.log import Log

log = Log('mwlib.jobsched')

# ==============================================================================


class JobScheduler(object):
    def __init__(self, num_threads, do_job):
        """
        @param num_threads: number of threads to start
        @type num_threads: int
        """
        
        self.num_threads = num_threads
        self.do_job = do_job
        self.job_queue = Queue.Queue()
        self.results = {}
        self.started = False
    
    def add_job(self, job_id, **kwargs):
        if not self.started:
            self.started = True
            for i in range(self.num_threads):
                JobThread(self).start()
            atexit.register(self.kill_threads)
        self.job_queue.put((job_id, kwargs))
    
    def get_results(self):
        """Wait for all queued jobs to be finished and return result dictionary
        
        @returns: dictionary containing results
        @rtype: dict
        """
        
        self.kill_threads()
        return self.results
    
    def kill_threads(self):
        if not self.started:
            return
        for i in range(self.num_threads):
            self.job_queue.put(('die', None))
        self.job_queue.join()
        self.started = False
    

# ==============================================================================


class JobThread(threading.Thread):
    def __init__(self, scheduler):
        super(JobThread, self).__init__()
        self.scheduler = scheduler
    
    def run(self):
        while True:
            job_id, kwargs = self.scheduler.job_queue.get()
            try:
                if job_id == 'die':
                    break
                try:                
                    self.scheduler.results[job_id] = self.scheduler.do_job(job_id, **kwargs)
                except Exception, exc:
                    log.ERROR('Error executing job: %s' % exc)
                    traceback.print_exc()
            finally:
                self.scheduler.job_queue.task_done()
    
