__version_info__ = (0, 15, 14)
display_version = version = __version__ = "0.15.14"
gitid = gitversion = ""

def main():
    import pkg_resources
    for r in ("mwlib", "mwlib.rl", "mwlib.ext", "mwlib.hiq"):
        try:
            v = pkg_resources.require(r)[0].version
            print r, v
        except:
            continue
