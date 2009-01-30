import os
if "MWREFINE" in os.environ:
    print "USING NEW REFINE PARSER"
    from mwlib.refine.uparser import simpleparse, parseString
else:
    from mwlib.old_uparser import simpleparse, parseString
