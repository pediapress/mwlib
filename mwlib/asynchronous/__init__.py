from __future__ import absolute_import
from apipkg import initpkg

initpkg(
    __name__,
    dict(
        jobs="qs.jobs",
        proc="qs.proc",
        qserve="qs.qserve",
        rpcclient="qs.rpcclient",
        rpcserver="qs.rpcserver",
        slave="qs.slave",
    ),
)
