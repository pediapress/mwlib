import optparse
try:
    import json
except ImportError:
    import simplejson as json

from mwlib.utils import start_logging
from mwlib import wiki, metabook, log

log = log.Log('mwlib.options')

class OptionParser(optparse.OptionParser):
    def __init__(self, usage=None, config_optional=False):
        self.config_optional = config_optional
        if usage is None:
            usage = '%prog [OPTIONS] [ARTICLETITLE...]'
        optparse.OptionParser.__init__(self, usage=usage)
        self.metabook = None
        self.add_option("-c", "--config",
            help="configuration file, ZIP file or base URL",
        )
        self.add_option("-i", "--imagesize",
            help="max. pixel size (width or height) for images (default: 800)",
            default=800,
        )
        self.add_option("-m", "--metabook",
            help="JSON encoded text file with article collection",
        )
        self.add_option('--collectionpage', help='Title of a collection page')
        self.add_option("-x", "--noimages",
            action="store_true",
            help="exclude images",
        )
        self.add_option("-l", "--logfile", help="log to logfile")
        self.add_option("--template-exclusion-category",
            help="Name of category for templates to be excluded",
            metavar='CATEGORY',
        )
        self.add_option("--print-template-prefix",
            help="Prefix for print templates",
            metavar='PREFIX',
        )
        self.add_option("--template-blacklist",
            help="Title of article containing blacklisted templates",
            metavar='ARTICLE',
        )
        self.add_option("--login",
            help='login with given USERNAME, PASSWORD and (optionally) DOMAIN',
            metavar='USERNAME:PASSWORD[:DOMAIN]',
        )
        self.add_option('--no-threads',
            action='store_true',
            help='do not use threads to fetch articles and images in parallel',
        )
        self.add_option('--num-threads',
            help='number of threads to fetch resources in parallel (default: 10)',
            default='10',
            metavar='NUM',
        )
        self.add_option("-d", "--daemonize", action="store_true",
            help='become a daemon process as soon as possible',
        )
        self.add_option('--pid-file',
            help='write PID of daemonized process to this file',
        )
        self.add_option('--title',
            help='title for article collection',
        )
        self.add_option('--subtitle',
            help='subtitle for article collection',
        )
        self.add_option('--editor',
            help='editor for article collection',
        )
        self.add_option('--script-extension',
            help='script extension for PHP scripts (default: .php)',
            default='.php',
        )
    
    def parse_args(self):
        self.options, self.args = optparse.OptionParser.parse_args(self)
        
        if self.options.logfile:
            start_logging(self.options.logfile)
        
        if self.options.config is None:
            if not self.config_optional:
                self.error('Please specify --config option. See --help for all options.')
            return self.options, self.args
        
        if self.options.metabook:
            self.metabook = json.loads(open(self.options.metabook, 'rb').read())
        
        if self.options.login is not None and ':' not in self.options.login:
            self.error('Please specify username and password as USERNAME:PASSWORD.')
        
        try:
            self.options.imagesize = int(self.options.imagesize)
            assert self.options.imagesize > 0
        except (ValueError, AssertionError):
            self.error('Argument for --imagesize must be an integer > 0.')
        
        try:
            self.options.num_threads = int(self.options.num_threads)
            assert self.options.num_threads >= 0
        except (ValueError, AssertionError):
            self.error('Argument for --num-threads must be an integer >= 0.')
        
        if self.options.no_threads:
            self.options.num_threads = 0
        
        if self.args:
            if self.metabook is None:
                self.metabook = metabook.make_metabook()
            for title in self.args:
                self.metabook['items'].append(metabook.make_article(
                    title=unicode(title, 'utf-8'),
                ))
        
        return self.options, self.args
    
    def makewiki(self):
        username, password, domain = None, None, None
        if self.options.login:
            if self.options.login.count(':') == 1:
                username, password = unicode(self.options.login, 'utf-8').split(':', 1)
            else:
                username, password, domain = unicode(self.options.login, 'utf-8').split(':', 2)
        if self.options.script_extension:
            script_extension = unicode(self.options.script_extension, 'utf-8')
        else:
            script_extension = None

        env = wiki.makewiki(self.options.config,
            metabook=self.metabook,
            username=username,
            password=password,
            domain=domain,
            script_extension=script_extension,
        )
        if self.options.noimages:
            env.images = None
        if self.options.template_blacklist:
            template_blacklist = unicode(self.options.template_blacklist, 'utf-8')
        else:
            template_blacklist = None
        if self.options.template_exclusion_category:
            template_exclusion_category = unicode(self.options.template_exclusion_category, 'utf-8')
        else:
            template_exclusion_category = None
        if self.options.print_template_prefix:
            print_template_prefix = unicode(self.options.print_template_prefix, 'utf-8')
        else:
            print_template_prefix = None
        if template_blacklist\
            or template_exclusion_category\
            or print_template_prefix:
            if hasattr(env.wiki, 'setTemplateExclusion'):
                env.wiki.setTemplateExclusion(
                    blacklist=template_blacklist,
                    category=template_exclusion_category,
                    prefix=print_template_prefix,
                )
            else:
                log.warn('WikiDB does not support setting a template blacklist')
        if self.options.collectionpage:
            wikitext = env.wiki.getRawArticle(unicode(self.options.collectionpage, 'utf-8'))
            if wikitext is None:
                raise RuntimeError('No such collection page: %r' % (
                    self.options.collectionpage,
                ))
            self.metabook = metabook.parse_collection_page(wikitext)
            env.metabook = self.metabook
        
        if self.options.title:
            env.metabook['title'] = unicode(self.options.title, 'utf-8')
        if self.options.subtitle:
            env.metabook['subtitle'] = unicode(self.options.subtitle, 'utf-8')
        if self.options.editor:
            env.metabook['editor'] = unicode(self.options.editor, 'utf-8')
        
        return env
    
