
import sys

from mwlib.utils._conf import ConfMod

sys.modules[__name__] = ConfMod(__name__)
