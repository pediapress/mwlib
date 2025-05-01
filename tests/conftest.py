import os
import sys

import gevent
import greenlet
import pytest

xnet = os.environ.get("XNET", "")  # eXclude NETwork tests
try:
    xnet = int(xnet)
except ValueError:
    pass

sys.path.append(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="session")
def alarm(request):
    import math
    import signal
    import time

    def sighandler(signum, frame):
        __tracebackhide__ = True
        raise RuntimeError("timeout after %s seconds" % (time.time() - stime))

    def cleanup():
        if hasattr(signal, "setitimer"):
            signal.setitimer(signal.ITIMER_REAL, 0)
        else:
            signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)

    def alarm(secs):
        if hasattr(signal, "setitimer"):
            signal.setitimer(signal.ITIMER_REAL, secs)
        else:
            signal.alarm(math.ceil(secs))

    request.addfinalizer(cleanup)
    stime = time.time()
    old_handler = signal.signal(signal.SIGALRM, sighandler)
    return alarm


def pytest_configure(config):
    kw = config.getvalue("keyword")
    if "xnet" in kw:
        return

    if xnet:
        print("conftest.py: disabling tests marked with keyword xnet.")
        print("conftest.py: set environment variable XNET=0 to enable them.")

        if kw:
            kw = kw + " -xnet"
        else:
            kw = "-xnet"
        config.option.keyword = kw


def pytest_report_header(config):
    return "gevent %s  --  greenlet %s" % (gevent.__version__, greenlet.__version__)


class Snippet:
    def __init__(self, txt, snippet_id):
        self.txt = txt
        self.snippet_id = snippet_id

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.snippet_id!r} {self.txt[:10]!r}...>"


def fetch_snippets():
    snippet_filepath = os.path.join(os.path.dirname(__file__), "mwlib", "rl", "snippets.txt")
    with open(snippet_filepath, encoding='utf-8') as snippet_file:
        examples = snippet_file.read().split("\x0c\n")[1:]
    res = []
    for i, example in enumerate(examples):
        if not example:
            continue
        res.append(Snippet(example, i))
    return res


@pytest.fixture(params=fetch_snippets())
def snippet(request):
    return request.param
