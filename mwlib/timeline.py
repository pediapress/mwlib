#! /usr/bin/env python

import os
import md5

basedir = os.path.expanduser("~/timeline")
assert os.path.isdir(basedir), "make sure %s exists and is a directory" % basedir

def drawTimeline(script):
    if isinstance(script, unicode):
        script = script.encode('utf8')
    
    m=md5.new()
    m.update(script)
    ident = m.hexdigest()

    pngfile = os.path.join(basedir, ident+'.png')
    
    if os.path.exists(pngfile):
        return pngfile

    scriptfile = os.path.join(basedir, ident+'.txt')
    open(scriptfile, 'w').write(script)
    err = os.system("easy-timeline.pl -T /tmp/ -i %s" % scriptfile)
    if err != 0:
        return None

    svgfile = os.path.join(basedir, ident+'.svg')

    if os.path.exists(svgfile):
        os.unlink(svgfile)

    if os.path.exists(pngfile):
        return pngfile

    return None

    
