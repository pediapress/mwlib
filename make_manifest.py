#! /usr/bin/env python

import os

def main():
    files = [x.strip() for x in os.popen("hg manifest")]
    files.append("README.html")
    def remove(n):
        try:
            files.remove(n)
        except ValueError:
            pass
    
    remove("make_manifest.py")
    remove(".hgtags")
    remove("Makefile")

    files.sort()

    f = open("MANIFEST.in", "w")
    for x in files:
        f.write("include %s\n" % x)
    f.close()


if __name__=='__main__':
    main()
