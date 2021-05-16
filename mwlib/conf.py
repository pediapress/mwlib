from __future__ import absolute_import

import sys

from mwlib._conf import ConfMod

sys.modules[__name__] = ConfMod(__name__)
