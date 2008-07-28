import py
import os
xmllint_not_found = os.system('xmllint --version 2>/dev/null 1>/dev/null')
ploticus_not_found = not os.path.isfile('/usr/bin/ploticus')

class Exclude(py.test.collect.Directory):
    def filefilter(self, path):
        if path.basename == 'test_xhtmlwriter.py' and xmllint_not_found:
            print "Skipping", path, "no xmllint found"
            return False
        if path.basename == 'test_timeline.py' and ploticus_not_found:
            print "Skipping", path, "no ploticus found"
            return False
        
        return super(Exclude, self).filefilter(path)

Directory = Exclude
