"""Configuration utilities for mwlib.

This module provides utilities for handling configuration settings from
environment variables and ini files.
"""

import os
import types

import py


def as_bool(val):
    """Convert a string value to a boolean.

    Args:
        val: A string value to convert to boolean.

    Returns:
        bool: True if the string represents a positive value 
        ("yes", "true", "on", "1"), False otherwise.
    """
    val = val.lower()
    if val in ("yes", "true", "on", "1"):
        return True
    if val in ("no", "false", "off", "0"):
        return False

    return False


class ConfBase:
    """Base configuration class for mwlib.

    This class provides methods to read configuration from ini files and
    environment variables.
    """

    def __init__(self):
        """Initialize a new ConfBase instance.

        The configuration is initially empty until readrc() is called.
        """
        self._inicfg = None

    def readrc(self, path=None):
        """Read configuration from an ini file.

        Args:
            path: Path to the ini file. If None, uses ~/.mwlibrc if it exists.
        """
        if path is None:
            path = os.path.expanduser("~/.mwlibrc")
            if not os.path.exists(path):
                return
        self._inicfg = py.iniconfig.IniConfig(path, None)

    def get(self, section, name, default=None, convert=str):
        """Get a configuration value.

        Looks for the value in environment variables first, then in the ini file.
        Environment variables are named MWLIB_SECTION_NAME or MWLIB_NAME (if section is "mwlib").

        Args:
            section: Section name in the ini file.
            name: Configuration key name.
            default: Default value if the key is not found.
            convert: Function to convert the string value to the desired type.

        Returns:
            The configuration value converted to the appropriate type, or the default value.
        """
        if section == "mwlib":
            varname = f"MWLIB_{name.upper()}"
        else:
            varname = f"MWLIB_{section.upper()}_{name.upper()}"

        if varname in os.environ:
            return convert(os.environ[varname])
        if self._inicfg is not None:
            return self._inicfg.get(section, name, default=default,
                                    convert=convert)
        return default

    @property
    def noedits(self):
        """Get the noedits configuration value.

        Returns:
            bool: True if edits should be disabled, False otherwise.
        """
        return self.get("fetch", "noedits", False, as_bool)

    @property
    def user_agent(self):
        """Get the user agent string for HTTP requests.

        Returns:
            str: The configured user agent or a default one based on the mwlib version.
        """
        from mwlib.utils._version import version

        return self.get("mwlib", "user_agent", "") or f"mwlib {version}"


class ConfMod(ConfBase, types.ModuleType):
    """Configuration module class.

    This class combines ConfBase with ModuleType to allow the configuration
    to be used as a Python module.
    """

    def __init__(self, *args, **kwargs):
        """Initialize a new ConfMod instance.

        Args:
            *args: Arguments to pass to ModuleType.__init__.
            **kwargs: Keyword arguments to pass to ModuleType.__init__.
        """
        ConfBase.__init__(self)
        types.ModuleType.__init__(self, *args, **kwargs)
        self.__file__ = __file__
