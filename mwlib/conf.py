import sys
from mwlib._conf import confmod

sys.modules[__name__] = confmod(__name__)
