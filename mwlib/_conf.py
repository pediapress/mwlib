import types, os, py


def as_bool(val):
    val = val.lower()
    if val in ("yes", "true", "on", "1"):
        return True
    if val in ("no", "false", "off", "0"):
        return False

    return False


class confbase(object):
    def __init__(self):
        self._inicfg = None

    def readrc(self, path=None):
        if path is None:
            path = os.path.expanduser("~/.mwlibrc")
            if not os.path.exists(path):
                return
        self._inicfg = py.iniconfig.IniConfig(path, None)

    def get(self, section, name, default=None, convert=str):
        if section == "mwlib":
            varname = "MWLIB_%s" % name.upper()
        else:
            varname = "MWLIB_%s_%s" % (section.upper(), name.upper())

        if varname in os.environ:
            return convert(os.environ[varname])
        if self._inicfg is not None:
            return self._inicfg.get(section, name, default=default, convert=convert)
        return default

    @property
    def noedits(self):
        return self.get("fetch", "noedits", False, as_bool)


class confmod(confbase, types.ModuleType):
    def __init__(self, *args, **kwargs):
        confbase.__init__(self)
        types.ModuleType.__init__(self, *args, **kwargs)
        self.__file__ = __file__
