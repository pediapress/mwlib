from apipkg import initpkg

__all__ = ["jobs", "proc", "qserve", "rpcclient", "rpcserver", "slave"]

initpkg(
    __name__,
    {
        "jobs": "qs.jobs",
        "proc": "qs.proc",
        "qserve": "qs.qserve",
        "rpcclient": "qs.rpcclient",
        "rpcserver": "qs.rpcserver",
        "slave": "qs.slave",
    },
)
