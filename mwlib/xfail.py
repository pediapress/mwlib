class UnexpectedSuccess(Exception):
    pass

class _stats(object):
    pass

stats = _stats()
stats.xfail = 0

def report():
    if stats.xfail:
        print stats.xfail, "expected failures"

import atexit
atexit.register(report)

def xfail(fun): # FIXME: what about generators?
    import os
    if 'XFAIL' in os.environ:
        def doit():
            try:
                fun()
            except:
                stats.xfail += 1
                return
            raise UnexpectedSuccess('expected %r to fail' % (fun,))
        return doit
    return fun
