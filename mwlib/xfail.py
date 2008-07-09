class UnexpectedSuccess(Exception):
    pass

def xfail(fun): # FIXME: what about generators?
    import os
    if 'XFAIL' in os.environ:
        def doit():
            try:
                fun()
            except:
                return
            raise UnexpectedSuccess('expected %r to fail' % (fun,))
        return doit
    return fun
