import py
import os
xmllint_not_found = os.system('xmllint --version 2>/dev/null 1>/dev/null')
ploticus_not_found = not os.path.isfile('/usr/bin/ploticus')
mathrenderer_not_found =  os.system('blahtexml --help 2>/dev/null 1>/dev/null')

xnet = os.environ.get("XNET", "") # eXclude NETwork tests
try:
    xnet = int(xnet)
except ValueError:
    pass

try:
    import lxml
except ImportError:
    lxml = None

class Exclude(py.test.collect.Directory):
    def consider_file(self, path):
        bn = path.basename
        
        if bn == 'test_xhtmlwriter.py' and xmllint_not_found:
            print "Skipping", bn, "-- no xmllint found"
            return []
        if bn == 'test_timeline.py' and ploticus_not_found:
            print "Skipping", bn, "-- no ploticus found"
            return []
        if bn == 'test_mathutils.py' and mathrenderer_not_found:
            print "Skipping", bn, '-- blahtexml or texvc for math rendering not found'
            return []
        if not lxml and bn=='test_docbookwriter.py':
            #print "Skipping", bn, "-- lxml not found"
            return []

        return py.test.collect.Directory.consider_file(self, path)

Directory = Exclude
import sys
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
