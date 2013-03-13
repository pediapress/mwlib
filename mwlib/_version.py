__version_info__ = (0, 15, 3)
version = __version__ = "0.15.3"

try:
    from mwlib._gitversion import gitid, gitversion
except ImportError:
    gitid = gitversion = ""

display_version = gitversion or version



def main():
    msg = "mwlib: %s" % (version or gitversion,)
    if gitid:
        msg += "(%s)" % gitid
    print msg

    try:
        from mwlib.rl import _gitversion
        print "mwlib.rl", _gitversion.gitversion
    except ImportError:
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

    try:
        from mwlib.hiq import _gitversion
    except ImportError:
        pass
    else:
        print "mwlib.hiq", _gitversion.gitversion
