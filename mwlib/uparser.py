
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.txt for additional licensing information.

import os

use_mwrefine = (os.environ.get("MWREFINE", "").lower()!="no")

if use_mwrefine:
    from mwlib.refine.uparser import simpleparse, parseString
else:
    import sys
    sys.stderr.write("USING OLD PARSER\n")
    from mwlib.old_uparser import simpleparse, parseString
