
import sys

from mwlib.configuration._conf import ConfMod

sys.modules[__name__] = ConfMod(__name__)
