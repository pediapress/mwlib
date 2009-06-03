import py
import os
xmllint_not_found = os.system('xmllint --version 2>/dev/null 1>/dev/null')
ploticus_not_found = not os.path.isfile('/usr/bin/ploticus')
mathrenderer_not_found =  os.system('blahtexml --help 2>/dev/null 1>/dev/null')

xnet = 'XNET' in os.environ # eXclude NETwork tests

try:
    import lxml
except ImportError:
    lxml = None

lxml = None # someplease please fix those docbookwriter tests

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
        if xnet and bn in ('test_mwapidb.py', 'test_zipwiki.py'):
            print "Skipping", bn, "-- needs network"
            return []

        return py.test.collect.Directory.consider_file(self, path)

Directory = Exclude
pytest_plugins = "pytest_twisted"
