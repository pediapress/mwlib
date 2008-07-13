import heapq
import os
import subprocess
import time
import traceback

from mwlib.log import Log
from mwlib import utils


class FileJobQueuer(object):
    """Write a file for each new job request"""
    
    def __init__(self, queue_dir):
        self.queue_dir = utils.ensure_dir(queue_dir)
    
    def __call__(self, job_type, job_id, args):
        job_file = os.path.join(self.queue_dir, job_id)
        if os.path.exists(job_file):
            raise RuntimeError('Job file %r already exists' % job_file)
        open(job_file, 'wb').write('\n'.join(args))


class FileJobPoller(object):
    def __init__(self, queue_dir, processing_dir, sleep_time=1, max_num_jobs=5):
        self.queue_dir = utils.ensure_dir(queue_dir)
        self.processing_dir = utils.ensure_dir(processing_dir)
        self.sleep_time = sleep_time
        self.max_num_jobs = max_num_jobs
        self.num_jobs = 0
        self.log = Log('FileJobPoller')
    
    def run_forever(self):
        self.log.info('running with a max. of %d jobs' % self.max_num_jobs)
        try:
            while True:
                filename = self.poll()
                if self.num_jobs < self.max_num_jobs and filename:
                    self.num_jobs += 1
                    self.start_job(filename)
                    self.log.info('child started: have %d jobs' % self.num_jobs)
                else:
                    time.sleep(self.sleep_time)
                while self.num_jobs > 0:
                    pid, rc = os.waitpid(-1, os.WNOHANG)
                    if (pid, rc) == (0, 0):
                        break
                    self.num_jobs -= 1
                    self.log.info('child killed: have %d jobs' % self.num_jobs)
        except KeyboardInterrupt:
            while self.num_jobs > 0:
                os.waitpid(-1, 0)
                self.num_jobs -= 1
        self.log.info('exit')
    
    def poll(self):
        files = []
        for filename in os.listdir(self.queue_dir):
            path = os.path.join(self.queue_dir, filename)
            if not os.path.isfile(path):
                continue
            heapq.heappush(files, (os.stat(path).st_mtime, filename))
        if files:
            return files[0][1]
        return None
    
    def start_job(self, filename):
        src = os.path.join(self.queue_dir, filename)
        path = os.path.join(self.processing_dir, filename)
        try:
            os.rename(src, path)
        except Exception, exc:
            self.log.warn('Could not rename %r to %r: %s' % (src, path, exc))
            traceback.print_exc()
            return
        self.log.info('starting job %r' % filename)
        pid = os.fork()
        if pid == 0:
            try:
                args = open(path, 'rb').read().split('\n')
                self.log.info('executing: %r' % args)
                try:
                    rc = subprocess.call(args)
                    assert rc == 0, 'non-zero return code'
                except Exception, exc:
                    self.log.warn('Error executing %r: %s' % (args, exc))
                    traceback.print_exc()
            finally:
                try:
                    os.unlink(path)
                except Exception, exc:
                    self.log.warn('Could not remove file %r: %s' % (path, exc))
                    traceback.print_exc()
                os._exit(0)
    
