from apipkg import initpkg
initpkg(
    __name__,
    dict(
        jobs = "qs.jobs",
        proc = "qs.proc.py",
        qserve = "qs.qserve.py",
        rpcclient = "qs.rpcclient",
        rpcserver = "qs.rpcserver",
        slave = "qs.slave"))
