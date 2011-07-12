import os, sys

xnet = os.environ.get("XNET", "") # eXclude NETwork tests
try:
    xnet = int(xnet)
except ValueError:
    pass

sys.path.append(os.path.dirname(os.path.abspath(__file__)))


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
