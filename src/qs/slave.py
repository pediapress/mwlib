#! /usr/bin/env python
import contextlib
import os
import sys
import time
import traceback

from qs.log import root_logger
from qs.rpcclient import ServerProxy

logger = root_logger.getChild(__name__)


def short_err_msg():
    etype, val, tb = sys.exc_info()
    msg = []
    a = msg.append

    a(etype.__name__)
    a(": ")
    a(str(val))

    file, lineno, name, _ = traceback.extract_tb(tb)[-1]
    a(f" in function {name}, file {file}, line {lineno}")

    return "".join(msg)


class Worker:
    def __init__(self, proxy):
        self.proxy = proxy

    def dispatch(self, job):
        self.job = job
        self.jobid = job["jobid"]
        self.priority = job["priority"]
        self.jobid_prefix = None

        method = job["channel"]
        method_name = f"rpc_{method}"

        m = getattr(self, method_name, None)
        if m is None:
            raise RuntimeError("no such method %r" % (method_name,))

        kwargs = job.get("payload") or dict()
        tmp = {}
        for k, v in list(kwargs.items()):
            if isinstance(k, str):
                tmp[str(k)] = v
            else:
                tmp[k] = v
        return m(**tmp)

    def q_set_info(self, info):
        return self.proxy.q_set_info(jobid=self.jobid, info=info)

    def qadd(
        self,
        channel,
        payload=None,
        jobid=None,
        prefix=None,
        wait=False,
        timeout=None,
        ttl=None,
    ):
        """call q_add on proxy with the same priority as the current job"""
        if jobid is None and prefix is not None:
            jobid = "%s::%s" % (prefix, channel)

        return self.proxy.qadd(
            channel=channel,
            payload=payload,
            priority=self.priority,
            jobid=jobid,
            wait=wait,
            timeout=timeout,
            ttl=ttl,
        )

    def qaddw(self, channel, payload=None, jobid=None, timeout=None):
        r = self.proxy.qadd(
            channel=channel,
            payload=payload,
            priority=self.priority,
            jobid=jobid,
            wait=True,
            timeout=timeout,
        )
        error = r.get("error")
        if error is not None:
            raise RuntimeError(error)

        return r["result"]


def main(  # noqa: C901
    commands,
    host="localhost",
    port=None,
    numthreads=10,
    num_procs=0,
    numgreenlets=0,
    argv=None,
):
    if port is None:
        port = 14311
    channels = []
    skip_channels = []

    if argv:
        import getopt

        try:
            opts, _ = getopt.getopt(
                argv,
                "c:s:",
                ["host=", "port=", "numthreads=", "numprocs=", "channel=", "skip="],
            )
        except getopt.GetoptError as err:
            logger.exception(str(err))
            sys.exit(10)

        for o, a in opts:
            if o == "--host":
                host = a
            if o == "--port":
                port = int(a)
            if o == "--numthreads":
                numthreads = int(a)
                num_procs = 0
            if o == "--numprocs":
                num_procs = int(a)
                numthreads = 0
            if o == "-c" or o == "--channel":
                channels.append(a)
            if o == "-s" or o == "--skip":
                skip_channels.append(a)

    class WorkHandler(Worker, commands):
        pass

    available_channels = []
    for x in dir(WorkHandler):
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

    if num_procs:

        def check_parent():
            if os.getppid() == 1:
                logger.error("parent died. exiting.")
                os._exit(0)

    else:

        def check_parent():
            #
            pass

    def handle_one_job(server_proxy: ServerProxy):
        logger.info("SLAVE HANDLING %s" % server_proxy)
        sleeptime = 0.5

        while 1:
            try:
                logger.info(f"pulling job from {host}:{port} for {channels}")
                job = server_proxy.qpull(channels=channels)
                logger.info("job: %s" % job)
                break
            except Exception as err:
                check_parent()
                logger.error("Error while calling pulljob: %s" % err)
                time.sleep(sleeptime)
                check_parent()
                if sleeptime < 60:
                    sleeptime *= 2

        check_parent()
        logger.info("got job: %s" % job)
        try:
            logger.info(server_proxy)
            result = WorkHandler(server_proxy).dispatch(job)
        except Exception as err:
            logger.error("error: %s" % err)
            try:
                server_proxy.qfinish(jobid=job["jobid"], error=short_err_msg())
                logger.exception("error while handling job")
            except Exception:
                pass
            return

        with contextlib.suppress(Exception):
            server_proxy.qfinish(jobid=job["jobid"], result=result)

    def start_worker():
        logger.info(f"Server proxy form start_worker {host}:{port}")
        qs = ServerProxy(host=host, port=port)
        while 1:
            handle_one_job(qs)

    channels_str = ", ".join(channels)
    logger.info(f"pulling jobs from {host}: {port} for {channels_str}")

    def run_with_threads():
        import threading

        for i in range(numthreads):
            logger.debug("starting thread %s" % i)
            t = threading.Thread(target=start_worker)
            t.start()

        try:
            while True:
                time.sleep(2**26)
        finally:
            os._exit(0)

    def run_with_procs():
        children = set()
        logger.info("Proc run")
        while 1:
            while len(children) < num_procs:
                try:
                    pid = os.fork()
                except Exception:
                    logger.info("failed to fork child")
                    time.sleep(1)
                    continue

                if pid == 0:
                    try:
                        logger.info(f"Server Proxy {host}:{port}")
                        qs = ServerProxy(host=host, port=port)
                        handle_one_job(qs)
                    finally:
                        os._exit(0)
                logger.debug("forked %s" % pid)
                children.add(pid)

            try:
                pid, _ = os.waitpid(-1, 0)
            except OSError:
                continue

            logger.debug("done %s" % pid)
            with contextlib.suppress(KeyError):
                children.remove(pid)

    def run_with_gevent():
        import gevent.pool

        from qs.misc import CallInLoop

        pool = gevent.pool.Pool()
        for i in range(numgreenlets):
            logger.debug("starting greenlet %s" % i)
            pool.spawn(CallInLoop(1.0, start_worker))

        pool.join()

    if numgreenlets > 0:
        run_with_gevent()
    elif num_procs > 0:
        run_with_procs()
    elif numthreads > 0:
        run_with_threads()
    else:
        assert 0, "bad"


if __name__ == "__main__":

    class Commands:
        def rpc_divide(self, a, b):
            logger.info(f"rpc_divide {a} {b}")
            return a // b

    main(Commands, num_procs=2)
