#! /usr/bin/env python


import os
import signal
import sys
import traceback

from gevent import Timeout, core, event, socket, version_info

from qs.log import root_logger

logger = root_logger.getChild(__name__)

if version_info[:2] >= (1, 0):
    from gevent import get_hub


pid2status = {}


def got_signal(*args):
    while 1:
        try:
            pid, st = os.waitpid(-1, os.WNOHANG)
            if pid == 0:
                return
            pid2status[pid].set(st)
        except OSError:
            return


_no_child = True
_initialized = False


def _init():
    global _initialized
    global _no_child
    if _initialized:
        return

    if version_info[:2] < (1, 0):
        core.event(core.EV_SIGNAL | core.EV_PERSIST, signal.SIGCHLD, got_signal).add()
    else:
        _no_child = getattr(get_hub().loop, "nochild", True)
        if _no_child:
            signal.signal(signal.SIGCHLD, got_signal)
    _initialized = True


def run_cmd(args, timeout=None):
    _init()
    args = list(args)
    for i, x in enumerate(args):
        if isinstance(x, str):
            args[i] = x.encode("utf-8")

    sp = socket.socketpair()
    pid = os.fork()
    if pid == 0:
        # client
        try:
            os.dup2(sp[1].fileno(), 1)
            os.dup2(sp[1].fileno(), 2)
            sp[0].close()
            sp[1].close()
            os.execvp(args[0], args)
        except Exception:
            stderr = os.fdopen(2, "w", 0)
            os.write(
                2, "failed to exec child process: %r\nPATH=%r" % (args, os.environ.get("PATH"))
            )
            traceback.print_exc(file=stderr)
            logger.exception("failed to exec child process: %r" % (args,))
        finally:
            os._exit(97)

    pid2status[pid] = event.AsyncResult()
    if not _no_child:

        def cb():
            pid2status[pid].set(child_watcher.rstatus)
            child_watcher.stop()

        child_watcher = get_hub().loop.child(pid)
        child_watcher.start(cb)

    sp[1].close()

    chunks = []

    # prevent loopexit. see test_run_cmd_trigger_loopexit in test_proc.py
    if timeout is None:
        timeout = 2 ** 30

    timeout = Timeout(timeout)
    timeout.start()
    try:
        while 1:
            chunk = sp[0].recv(4096)
            if not chunk:
                break
            chunks.append(chunk)

        st = pid2status[pid].get()
        del pid2status[pid]

        if int(sys.version[0]) < 3:
            return st, "".join(chunks)
        else:
            return st, (b"".join(chunks)).decode("utf-8")
    except Timeout as t:
        if t is not timeout:
            raise
    finally:
        timeout.cancel()

    os.kill(pid, 9)

    with Timeout(1):
        st = pid2status[pid].get()
        del pid2status[pid]
        return st, "".join(chunks)
