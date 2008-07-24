import optparse
import simplejson

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
        self.add_option("--template-blacklist",
            help="Title of article containing blacklisted templates",
        )
        self.add_option("--login",
            help='login with given USERNAME, PASSWORD and (optionally) DOMAIN',
            metavar='USERNAME:PASSWORD[:DOMAIN]',
        )
        self.add_option('--no-threads',
            action='store_true',
            help='do not use threads to fetch articles and images in parallel',
        )
        self.add_option('--num-article-threads',
            help='number of threads to fetch articles in parallel (default: 5)',
            default='3',
            metavar='NUM',
        )
        self.add_option('--num-image-threads',
            help='number of threads to fetch images in parallel (default: 5)',
            default='5',
            metavar='NUM',
        )
        self.add_option("-d", "--daemonize", action="store_true",
            help='become a daemon process as soon as possible',
        )
        self.add_option('--pid-file',
            help='write PID of daemonized process to this file',
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
            self.metabook = simplejson.loads(open(self.options.metabook, 'rb').read())
        
        if self.options.login is not None and ':' not in self.options.login:
            self.error('Please specify username and password as USERNAME:PASSWORD.')
        
        try:
            self.options.imagesize = int(self.options.imagesize)
            assert self.options.imagesize > 0
        except (ValueError, AssertionError):
            self.error('Argument for --imagesize must be an integer > 0.')
        
        try:
            self.options.num_article_threads = int(self.options.num_article_threads)
            assert self.options.num_article_threads >= 0
        except (ValueError, AssertionError):
            self.error('Argument for --num-article-threads must be an integer >= 0.')
        
        try:
            self.options.num_image_threads = int(self.options.num_image_threads)
            assert self.options.num_image_threads >= 0
        except (ValueError, AssertionError):
            self.error('Argument for --num-image-threads must be an integer >= 0.')
        
        if self.options.no_threads:
            self.options.num_article_threads = 0
            self.options.num_image_threads = 0
        
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
                username, password = self.options.login.split(':', 1)
            else:
                username, password, domain = self.options.login.split(':', 2)
        env = wiki.makewiki(self.options.config,
            metabook=self.metabook,
            username=username,
            password=password,
            domain=domain,
        )
        if self.options.noimages:
            env.images = None
        if self.options.template_blacklist:
            if hasattr(env.wiki, 'setTemplateBlacklist'):
                env.wiki.setTemplateBlacklist(self.options.template_blacklist)
            else:
                log.warn('WikiDB does not support setting a template blacklist')
        if self.options.collectionpage:
            wikitext = env.wiki.getRawArticle(self.options.collectionpage)
            if wikitext is None:
                raise RuntimeError('No such collection page: %r' % (
                    self.options.collectionpage,
                ))
            self.metabook = metabook.parse_collection_page(wikitext)
            env.metabook = self.metabook
        return env
    
