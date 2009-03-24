import py

try:
    xfail = py.test.mark.xfail("expected failure")
except Exception:
    from _xfail import xfail
    
