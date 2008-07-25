class UnexpectedSuccess(Exception):
    pass

class _stats(object):
    pass

stats = _stats()
stats.xfail = 0
stats.warnings = []

def report():
    if stats.xfail:
        print stats.xfail, "expected failures"
    print "\n".join(stats.warnings)
        
import atexit
atexit.register(report)

def xfail(fun): # FIXME: what about generators?
    import os
    doc = fun.__doc__ or ""
    if 'http://code.pediapress.com/wiki/ticket/' not in doc:
        stats.warnings.append("expected failure %s.%s does not reference a ticket in it's docstring" % (fun.__module__, fun.__name__,))
        
    if 'XFAIL' in os.environ:


        def doit(*args, **kwargs):
            try:
                fun(*args, **kwargs)
            except:
                stats.xfail += 1
                return
            raise UnexpectedSuccess('expected %r to fail' % (fun,))
        return doit
    return fun
