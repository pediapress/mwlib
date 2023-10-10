

import os
import time
import traceback

import six.moves.cPickle

from mwlib import utils
from mwlib.utilities.log import Log


class FileJobQueuer:
    """Write a file for each new job request"""

    def __init__(self, queue_dir):
        self.queue_dir = utils.ensure_dir(queue_dir)
        self.log = Log("FileJobQueuer")

    def __call__(self, _, job_id, args):
        job_filename = "%s.job" % os.path.join(self.queue_dir, job_id)
        if os.path.exists(job_filename):
            self.log.warn(f"Job file {job_filename} already exists")
            return

        with open(job_filename + ".tmp", "wb") as job_file:
            job_file.write(six.moves.cPickle.dumps(args))
        os.rename(job_filename + ".tmp", job_filename)


class FileJobPoller:
    def __init__(self, queue_dir, _=None, sleep_time=1, max_num_jobs=5):
        self.queue_dir = utils.ensure_dir(queue_dir)
        self.sleep_time = sleep_time
        self.max_num_jobs = max_num_jobs
        self.num_jobs = 0
        self.log = Log("FileJobPoller")
        self.files = []

    def _reap_children(self):
        while self.num_jobs > 0:
            try:
                flags = 0 if self.num_jobs == self.max_num_jobs else os.WNOHANG
                pid, exit_code = os.waitpid(-1, flags)
            except OSError as exc:
                self.log.ERROR(f"waitpid(-1) failed: {exc}")
                break
            if (pid, exit_code) == (0, 0):
                break
            self.num_jobs -= 1
            self.log.info(f"child {pid} exited: {exit_code}. have {self.num_jobs} jobs")

    def run_forever(self):
        self.log.info("running with a max. of %d jobs" % self.max_num_jobs)
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
            except Exception as err:
                self.log.error(f"caught exception: {err!r}")
                traceback.print_exc()

        self.log.info("exit")

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
            except Exception as exc:
                self.log.ERROR(f"Could not stat {path!r}: {exc}")
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
            with open(src, "rb") as job_file:
                args = six.moves.cPickle.loads(job_file.read())
        finally:
            os.unlink(src)

        self.log.info(f"starting job {filename}")

        pid = os.fork()
        self.num_jobs += 1

        if pid != 0:
            return True

        # child process:
        try:
            os.execvp(args[0], args)
        except BaseException:
            traceback.print_exc()
        finally:
            self.log.warn(f"error running {args!r}")
            os._exit(10)
        return False
