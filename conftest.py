import os, sys

xnet = os.environ.get("XNET", "") # eXclude NETwork tests
try:
    xnet = int(xnet)
except ValueError:
    pass

sys.path.append(os.path.dirname(os.path.abspath(__file__)))


def pytest_funcarg__alarm(request):
    import signal, time, math

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
        print "conftest.py: disabling tests marked with keyword xnet."
        print "conftest.py: set environment variable XNET=0 to enable them."
        
        if kw:
            kw = kw+" -xnet"
        else:
            kw = "-xnet"
        config.option.keyword = kw
