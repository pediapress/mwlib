import getopt
import os
import pickle
import sys

import gevent
import gevent.pool

from qs import jobs, misc, rpcserver
from qs.log import root_logger

logger = root_logger.getChild("qserve")


class db:
    def __init__(self):
        self.key2data = {}
        self.workq = jobs.workq()


class QPlugin:
    def __init__(self, **kw):
        self.running_jobs = {}

    def rpc_qadd(
        self,
        channel,
        payload=None,
        priority=0,
        jobid=None,
        wait=False,
        timeout=None,
        ttl=None,
    ):
        logger.info(f"add: {channel} {payload!r}")
        jobid = self.workq.push(
            payload=payload,
            priority=priority,
            channel=channel,
            jobid=jobid,
            timeout=timeout,
            ttl=ttl,
        )
        logger.info(f"jobid: {jobid}")
        if not wait:
            return jobid

        res = self.workq.waitjobs([jobid])[0]
        logger.info(f"waited: {res}")
        return res._json()

    def rpc_qpull(self, channels=None):
        if not channels:
            channels = []
        logger.info(f"pull {channels}")
        j = self.workq.pop(channels)
        self.running_jobs[j.jobid] = j
        logger.info(f"pulled {j}")
        return j._json()

    def rpc_qfinish(self, jobid, result=None, error=None, traceback=None):
        if error:
            logger.error(f"error finish: {jobid}: {error!r}")
        else:
            logger.info(f"finish: {jobid}: {result!r}")
        self.workq.finishjob(jobid, result=result, error=error)
        if jobid in self.running_jobs:
            del self.running_jobs[jobid]

    def rpc_qsetinfo(self, jobid, info):
        logger.info(f"setinfo: {jobid}: {info!r}")
        self.workq.updatejob(jobid, info)

    def rpc_qinfo(self, jobid):
        logger.info(f"info: {jobid}")
        if jobid in self.workq.id2job:
            return self.workq.id2job[jobid]._json()
        return None

    def rpc_qwait(self, jobids):
        logger.info("wait", jobids)
        res = self.workq.waitjobs(jobids)
        return [j._json() for j in res]

    def rpc_qkill(self, jobids):
        self.workq.killjobs(jobids)

        for jobid in jobids:
            if jobid in self.running_jobs:
                del self.running_jobs[jobid]

    def rpc_qdrop(self, jobids):
        self.workq.dropjobs(jobids)

    def rpc_qprefixmatch(self, prefix):
        logger.info("prefixmatch", prefix)
        return list(self.workq.prefixmatch(prefix))

    def rpc_getstats(self):
        return self.workq.getstats()

    def shutdown(self):
        for j in list(self.running_jobs.values()):
            logger.debug("reschedule %s" % j)
            self.workq.pushjob(j)


class Main:
    def __init__(self, port, interface, data_dir, allowed_ips):
        self.port = port
        self.interface = interface
        self.data_dir = data_dir
        self.allowed_ips = allowed_ips
        self.loaddb()

    def loaddb(self):
        data_dir = self.data_dir
        if data_dir is not None:
            if not os.path.isdir(data_dir):
                sys.exit(f"{data_dir!r} is not a directory")
            qpath = os.path.join(data_dir, "workq.pickle")
        else:
            qpath = None

        if qpath and os.path.exists(qpath):
            logger.info(f"loading {qpath}")
            q_file = open(qpath, "rb")  # noqa: SIM115
            self.db = pickle.load(q_file)
            logger.info(f"loaded {len(self.db.workq.id2job)} jobs")
        else:
            self.db = db()
        self.qpath = qpath

    def savedb(self):
        if self.qpath:
            logger.info(f"saving {self.qpath}")
            with open(self.qpath, "wb") as f:
                pickle.dump(self.db, f, 2)

    def is_allowed_ip(self, ip):
        return not self.allowed_ips or ip in self.allowed_ips

    def handletimeouts(self):
        self.db.workq.handletimeouts()

    def watchdog(self):
        self.db.workq.dropdead()

    def report(self):
        self.db.workq.report()
        pool = self.server.pool
        logger.debug("= %s clients" % len(pool))
        for cl in pool:
            logger.debug(cl)

    def run(self):
        class Handler(rpcserver.RequestHandler, QPlugin):
            def __init__(self, **kwargs):
                super(Handler, self).__init__(**kwargs)

            workq = self.db.workq
            db = self.db

        s = self.server = rpcserver.Server(
            self.port,
            host=self.interface,
            get_request_handler=Handler,
            is_allowed=self.is_allowed_ip,
        )
        self.port = s.stream_server.socket.getsockname()[1]
        logger.info(f"listening on {self.interface}:{self.port}")

        loops = [(self.report, 20), (self.watchdog, 15), (self.handletimeouts, 1)]
        workers = gevent.pool.Pool()
        for fun, sleeptime in loops:
            workers.spawn(misc.CallInLoop(sleeptime, fun))

        bs = None
        try:
            backdoor_port = port_from_str(os.environ.get("QSERVE_BACKDOOR", ""))
        except ValueError:
            pass
        else:
            from gevent import backdoor

            bs = backdoor.BackdoorServer(
                ("localhost", backdoor_port),
                locals={
                    "_main": self,
                    "workers": workers,
                    "server": s,
                    "workq": self.db.workq,
                },
            )
            bs.banner = "Welcome to qserve!"
            if hasattr(bs, "pre_start"):
                bs.pre_start()
            else:
                bs.init_socket()  # gevent >= 1.0b1
            logger.info(
                "starting backdoor on 127.0.0.1:%s" % bs.socket.getsockname()[1]
            )
            bs.start()

        try:
            s.run_forever()
        except KeyboardInterrupt:
            logger.info("interrupted")
        finally:
            self.savedb()
            workers.kill()
            if bs is not None:
                bs.kill()


def usage():
    print("mw-qserve [-p PORT] [-i INTERFACE] [-d DATADIR]")


def port_from_str(port):
    port = int(port)
    if port < 0 or port > 65535:
        raise ValueError("bad port")
    return port


def parse_options(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    try:
        opts, args = getopt.getopt(argv, "a:d:p:i:h", ["help", "port=", "interface="])
    except getopt.GetoptError as err:
        logger.info(str(err))
        sys.exit(10)

    if args:
        logger.info("too many arguments")
        sys.exit(10)

    port = 14311
    interface = "0.0.0.0"
    data_dir = None
    allowed_ips = set()

    for o, a in opts:
        if o in ("-p", "--port"):
            try:
                port = port_from_str(a)
            except ValueError:
                logger.info("expected positive integer as argument to %s" % o)
                sys.exit(10)
        elif o in ("-i", "--interface"):
            interface = a
        elif o in ("-d"):
            data_dir = a
        elif o in ("-a"):
            allowed_ips.add(a)
        elif o in ("-h", "--help"):
            usage()
            sys.exit(0)

    return {
        "port": port,
        "interface": interface,
        "data_dir": data_dir,
        "allowed_ips": allowed_ips,
    }


def main(argv=None):
    logger.info("starting qserve")
    Main(**parse_options(argv=argv)).run()


if __name__ == "__main__":
    main()
