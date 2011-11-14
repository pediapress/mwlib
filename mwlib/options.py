import sys
import optparse

from mwlib import myjson as json

from mwlib.utils import start_logging
from mwlib import wiki, metabook, log

log = log.Log('mwlib.options')


        
class OptionParser(optparse.OptionParser):
    def __init__(self, usage='%prog [OPTIONS] [ARTICLETITLE...]'):
        self.config_values = []
        
        optparse.OptionParser.__init__(self, usage=usage)
        
        self.metabook = None
        
        a = self.add_option
        
        a("-c", "--config", action="callback", nargs=1, type="string", callback=self._cb_config, 
          help="configuration file, ZIP file or base URL")
        
        a("-i", "--imagesize",
          default=1200,
          help="max. pixel size (width or height) for images (default: 1200)")
        
        a("-m", "--metabook",
          help="JSON encoded text file with article collection")
        
        a("--collectionpage", help="Title of a collection page")
        
        a("-x", "--noimages", action="store_true",
          help="exclude images")
        
        a("-l", "--logfile", help="log to logfile")
        
        a("--template-exclusion-category", metavar="CATEGORY", 
          help="Name of category for templates to be excluded")
        
        a("--print-template-prefix", metavar="PREFIX",
          help="Prefix for print templates (deprecated: use --print-template-pattern)")
        
        a("--print-template-pattern", metavar="SUBPAGE",
          help="Prefix for print templates, '$1' is replaced by original template name")
        
        a("--template-blacklist", metavar="ARTICLE",
          help="Title of article containing blacklisted templates")

        a("--username", help="username for login")
        a("--password", help="password for login")
        a("--domain",  help="domain for login")

        a("--title",
          help="title for article collection")
        
        a("--subtitle",
          help="subtitle for article collection")
        
        a("--editor",
          help="editor for article collection")
        
        a("--script-extension",
          default=".php",
          help="script extension for PHP scripts (default: .php)")
        
        
    def _cb_config(self, option, opt, value, parser):
        """handle multiple --config arguments by resetting parser.values and storing
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
        self.options, self.args = optparse.OptionParser.parse_args(self, args=[unicode(x, "utf-8") for x in sys.argv[1:]])
        for c in self.config_values:
            if not hasattr(c, "pages"):
                c.pages = []
            
        if self.options.logfile:
            start_logging(self.options.logfile)
        
        if self.options.metabook:
            self.metabook = json.loads(unicode(open(self.options.metabook, 'rb').read(), 'utf-8'))
        
        try:
            self.options.imagesize = int(self.options.imagesize)
            assert self.options.imagesize > 0
        except (ValueError, AssertionError):
            self.error('Argument for --imagesize must be an integer > 0.')
        
        for title in self.args:
            if self.metabook is None:
                self.metabook = metabook.collection()
            
            self.metabook.append_article(title)

        if self.options.print_template_pattern and "$1" not in self.options.print_template_pattern:
            self.error("bad --print-template-pattern argument [must contain $1, but %r does not]" % (self.options.print_template_pattern,))

        
        if self.options.print_template_prefix and self.options.print_template_pattern:
            log.warn('Both --print-template-pattern and --print-template-prefix (deprecated) specified. Using --print-template-pattern only.')
        elif self.options.print_template_prefix:
            self.options.print_template_pattern = '%s$1' % self.options.print_template_prefix

        del self.options.print_template_prefix
        
        return self.options, self.args
    
    def makewiki(self):
        kw = self.options.__dict__.copy()
        kw["metabook"] = self.metabook
        
        env = wiki.makewiki(**kw)
        
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
            mw_license_url = wiki.wpwikis.get(cfg[1:])['mw_license_url']
            env.metabook.licenses.append(dict(mw_license_url=mw_license_url,
                                              type="license"))

        return env
