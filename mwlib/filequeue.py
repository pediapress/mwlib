import os
import subprocess
import time
import traceback
import cPickle

from mwlib.log import Log
from mwlib import utils


class FileJobQueuer(object):
    """Write a file for each new job request"""
    
    def __init__(self, queue_dir):
        self.queue_dir = utils.ensure_dir(queue_dir)
        self.log = Log('FileJobQueuer')
    
    def __call__(self, job_type, job_id, args):
        job_file = '%s.job' % os.path.join(self.queue_dir, job_id)
        if os.path.exists(job_file):
            self.log.warn('Job file %r already exists' % job_file)
            return
        
        open(job_file + '.tmp', 'wb').write(cPickle.dumps(args))
        os.rename(job_file + '.tmp', job_file)


class FileJobPoller(object):
    def __init__(self, queue_dir, processing_dir=None, sleep_time=1, max_num_jobs=5):
        self.queue_dir = utils.ensure_dir(queue_dir)
        self.sleep_time = sleep_time
        self.max_num_jobs = max_num_jobs
        self.num_jobs = 0
        self.log = Log('FileJobPoller')
        self.files = []
        
    def _reap_children(self):
        while self.num_jobs>0:
            try:
                if self.num_jobs==self.max_num_jobs:
                    flags = 0
                else:
                    flags = os.WNOHANG
                pid, rc = os.waitpid(-1, flags)
            except OSError, exc:
                self.log.ERROR('waitpid(-1) failed: %s' % exc)
                break
            if (pid, rc) == (0, 0):
                break
            self.num_jobs -= 1
            self.log.info('child %s exited: %s. have %d jobs' % (pid, rc, self.num_jobs))
            
    def run_forever(self):
        self.log.info('running with a max. of %d jobs' % self.max_num_jobs)
        while True:
            try:
                self.poll()
                if not self.files:
                    time.sleep(self.sleep_time)
                
                while self.num_jobs < self.max_num_jobs and self.files:
                    self.start_job(self.files.pop())

                self._reap_children()
            except KeyboardInterrupt:
                while self.num_jobs > 0:
                    os.waitpid(-1, 0)
                    self.num_jobs -= 1
                break
            except Exception, err:
                self.log.error("caught exception: %r" % (err, ))
                traceback.print_exc()
                    
        self.log.info('exit')
    
    def poll(self):
        if self.files:
            return
        
        files = []
        for filename in os.listdir(self.queue_dir):
            if filename.endswith(".tmp"):
                continue
            
            path = os.path.join(self.queue_dir, filename)
            if not os.path.isfile(path):
                continue
            try:
                mtime = os.stat(path).st_mtime
            except Exception, exc:
                self.log.ERROR('Could not stat %r: %s' % (path, exc))
                continue
            files.append((mtime, filename))

        files.sort(reverse=True)
        self.files = [x[1] for x in files]
    
    def start_job(self, filename):
        """Fork, and execute job from given file
        
        @returns: whether a new job as been started
        @rtype: bool
        """

        src = os.path.join(self.queue_dir, filename)
        try:
            args = cPickle.loads(open(src, 'rb').read())
        finally:
            os.unlink(src)
        
        self.log.info('starting job %r' % filename)
        
        pid = os.fork()
        self.num_jobs+=1
        
        if pid != 0:
            return True

        # child process:
        try:
            os.execvp(args[0], args)
        except:
            traceback.print_exc()
        finally:
            self.log.warn('error running %r' % (args,))
            os._exit(10)
