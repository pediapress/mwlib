import optparse
import sys

from mwlib import log, metabook, wiki
from mwlib import myjson as json
from mwlib.utils import start_logging

log = log.Log("mwlib.options")


class OptionParser(optparse.OptionParser):
    def __init__(self, usage="%prog [OPTIONS] [ARTICLETITLE...]"):
        self.config_values = []
        optparse.OptionParser.__init__(self, usage=usage)
        self.metabook = None
        arg = self.add_option

        arg(
            "-c",
            "--config",
            action="callback",
            nargs=1,
            type="string",
            callback=self._cb_config,
            help="configuration file, ZIP file or base URL",
        )

        arg(
            "-i",
            "--imagesize",
            default=1200,
            help="max. pixel size (width or height) for images (default: 1200)",
        )

        arg("-m", "--metabook", help="JSON encoded text file with article collection")

        arg("--collectionpage", help="Title of a collection page")

        arg("-x", "--noimages", action="store_true", help="exclude images")

        arg("-l", "--logfile", help="log to logfile")

        arg("--username", help="username for login")
        arg("--password", help="password for login")
        arg("--domain", help="domain for login")

        arg("--title", help="title for article collection")

        arg("--subtitle", help="subtitle for article collection")

        arg("--editor", help="editor for article collection")

        arg(
            "--script-extension",
            default=".php",
            help="script extension for PHP scripts (default: .php)",
        )

    def _cb_config(self, _, opt, value, parser):
        """handle multiple --config arguments by
        resetting parser.values and storing
        the old value in parser.config_values"""

        import copy

        config_values = parser.config_values

        if not config_values:
            parser.config_values.append(parser.values)

        config_values[-1] = copy.deepcopy(config_values[-1])

        if parser.values.config:
            del parser.largs[:]

        parser.values.__dict__ = copy.deepcopy(config_values[0].__dict__)

        config_values.append(parser.values)

        parser.values.config = value
        parser.values.pages = parser.largs

    def parse_args(self):
        self.options, self.args = optparse.OptionParser.parse_args(
            self, args=list(sys.argv[1:])
        )
        for config in self.config_values:
            if not hasattr(config, "pages"):
                config.pages = []

        if self.options.logfile:
            start_logging(self.options.logfile)

        if self.options.metabook:
            if "{" in self.options.metabook and "}" in self.options.metabook:
                self.metabook = json.loads(self.options.metabook)
            else:
                with open(self.options.metabook) as fp:
                    self.metabook = json.load(fp)

        try:
            self.options.imagesize = int(self.options.imagesize)
            if self.options.imagesize <= 0:
                raise ValueError()
        except (ValueError):
            self.error("Argument for --imagesize must be an integer > 0.")

        for title in self.args:
            if self.metabook is None:
                self.metabook = metabook.collection()

            self.metabook.append_article(title)

        return self.options, self.args

    def make_wiki(self):
        kw = self.options.__dict__.copy()
        kw["metabook"] = self.metabook

        env = wiki.make_wiki(**kw)

        if not env.metabook:
            self.metabook = env.metabook = metabook.collection()
            env.init_metabook()

        if self.options.noimages:
            env.images = None

        def setmb(name):
            n = getattr(self.options, name)
            if n:
                env.metabook[name] = n

        setmb("title")
        setmb("subtitle")
        setmb("editor")

        # add default licenses
        cfg = self.options.config or ""

        if cfg.startswith(":") and not env.metabook.licenses:
            mw_license_url = wiki.wpwikis.get(cfg[1:])["mw_license_url"]
            env.metabook.licenses.append({"mw_license_url": mw_license_url,
                                          "type": "License"})

        return env
