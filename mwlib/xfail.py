import py
try:
    xfail = py.test.mark.xfail("expected failure")
except AttributeError:
    xfail = py.test.xfail
    
