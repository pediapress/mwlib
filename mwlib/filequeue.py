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
                    if self.start_job(filename):
                        self.log.info('child started: have %d jobs' % self.num_jobs)
                    else:
                        # job has not been started
                        self.num_jobs -= 1
                else:
                    time.sleep(self.sleep_time)
                while self.num_jobs > 0:
                    try:
                        pid, rc = os.waitpid(-1, os.WNOHANG)
                    except OSError, exc:
                        self.log.ERROR('waitpid(-1) failed: %s' % exc)
                        break
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
            
        if files:
            return min(files)[1]
        return None
    
    def start_job(self, filename):
        """Fork, and execute job from given file
        
        @returns: whether a new job as been started
        @rtype: bool
        """

        src = os.path.join(self.queue_dir, filename)
        path = os.path.join(self.processing_dir, filename)
        try:
            os.rename(src, path)
        except Exception, exc:
            self.log.ERROR('Could not rename %r to %r: %s' % (src, path, exc))
            return False
        self.log.info('starting job %r' % filename)
        try:
            pid = os.fork()
        except Exception, exc:
            self.log.ERROR('Could not fork(): %s' % exc)
            return False
        if pid != 0:
            return True

        # child process:
        try:
            args = cPickle.loads(open(path, 'rb').read())
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

