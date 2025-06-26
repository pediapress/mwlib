import sys

from mwlib.utils._conf import ConfMod

# This is an unusual but powerful pattern: we replace the current module in sys.modules
# with an instance of ConfMod. This allows other modules to import and use 'conf' directly
# as a configuration object without having to create an instance first.
#
# Example usage in other modules:
#   from mwlib.utils import conf
#   value = conf.get('section', 'option')
#   # Or access sections directly as attributes:
#   value = conf.section.option
sys.modules[__name__] = ConfMod(__name__)
