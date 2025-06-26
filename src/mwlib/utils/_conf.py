import configparser
import logging
import os

from mwlib.utils._version import version

logger = logging.getLogger("mwlib.utils.conf")


class ConfigSection:
    """Wrapper for a config section to allow attribute-style access to options."""

    def __init__(self, section):
        self._section = section

    def __getattr__(self, name):
        if name in self._section:
            return self._section[name]
        raise AttributeError(f"No option '{name}' in this section")

    def __getitem__(self, key):
        return self._section[key]

    def get(self, option, fallback=None):
        return self._section.get(option, fallback)

    def getint(self, option, fallback=None):
        return self._section.getint(option, fallback)

    def getfloat(self, option, fallback=None):
        return self._section.getfloat(option, fallback)

    def getboolean(self, option, fallback=None):
        return self._section.getboolean(option, fallback)


class ConfMod:
    def __init__(self, name):
        self.__name__ = name

        default_config = {
            "DEFAULT": {
                "user_agent": f"mwlib {version}",
                "version": f"mwlib {version}",
            },
            "fetch": {
                "noedits": "False",
            },
        }

        self.config = configparser.ConfigParser()
        self.config.read_dict(default_config)

        # Try to load from config files
        config_files = [
            os.path.expanduser("~/.mwlibrc"),  # User-specific config
            "/etc/mwlib.ini",  # System-wide config
            "mwlib.ini",  # Local directory config
        ]
        found_files = self.config.read(config_files)
        logger.debug(f"found {len(found_files)} config files: {found_files}")

        # Override with environment variables
        self._load_from_env()

    def _load_from_env(self):
        """Load configuration from environment variables.

        Format: MWLIB_SECTION_OPTION=value
        Example: MWLIB_DEFAULT_DEBUG=true will set config['DEFAULT']['debug'] = 'true'
        """
        prefix = "MWLIB_"  # Change this to your app's prefix

        for key, value in os.environ.items():
            if key.startswith(prefix):
                parts = key[len(prefix) :].lower().split("_", 1)
                if len(parts) == 2:
                    section, option = parts
                    if not self.config.has_section(section) and section.lower() != "default":
                        self.config.add_section(section)
                    self.config[section][option] = value

    def get(self, section, option, fallback=None, type_=str):
        """Get a configuration value with type conversion."""
        try:
            if type_ is bool:
                return self.config.getboolean(section, option)
            elif type_ is int:
                return self.config.getint(section, option)
            elif type_ is float:
                return self.config.getfloat(section, option)
            else:
                return self.config.get(section, option)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return fallback

    def __getattr__(self, name):
        # This allows accessing config sections as attributes
        # e.g., conf.general.debug instead of conf.get('general', 'debug')
        if name in self.config:
            return ConfigSection(self.config[name])
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    def __getitem__(self, section):
        # Allow dictionary-style access to sections
        return self.config[section]

    @property
    def noedits(self):
        return self.get("fetch", "noedits", False, bool)

    @property
    def version(self):
        return self.get("DEFAULT", "version", "")

    @property
    def user_agent(self):
        return self.get("DEFAULT", "user_agent", "")
