import py
import os
xmllint_not_found = os.system('xmllint --version 2>/dev/null 1>/dev/null')

class Exclude(py.test.collect.Directory):
    def filefilter(self, path):
        if path.basename == 'test_odfwriter.py':
            print "Skipping", path, "broken beyond belief"
            return False
        if path.basename == 'test_xhtmlwriter.py' and xmllint_not_found:
            print "Skipping", path, "no xmllint found"
            return False
        
        return super(Exclude, self).filefilter(path)

Directory = Exclude
