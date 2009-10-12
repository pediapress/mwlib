class _Version(tuple):
    """internal version object, subclass of C{tuple},
    but implements a fancier __str__ representation
    """
    def __str__(self):
        return '.'.join([str(x) for x in self])

version = _Version((0,12,9))
del _Version

try:
    from mwlib._gitversion import gitid, gitversion
except ImportError:
    gitid = gitversion = ""

display_version = gitversion or str(version)

def main():
    print "mwlib: %s (%s)" % (display_version, gitid)
    try:
        from mwlib.rl._version import version as rlversion
        print "mwlib.rl:", rlversion
    except ImportError:
        pass

    try:
        from mwlib._extversion import version as extversion
        print "mwlib.ext:", extversion
    except ImportError:
        pass
