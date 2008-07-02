import optparse
import simplejson

from mwlib.utils import start_logging
from mwlib import wiki, metabook, log

log = log.Log('mwlib.options')

class OptionParser(optparse.OptionParser):
    def __init__(self, usage=None, conf_optional=False):
        self.conf_optional = conf_optional
        if usage is None:
            usage = '%prog [OPTIONS] [ARTICLETITLE...]'
        optparse.OptionParser.__init__(self, usage=usage)
        self.metabook = None
        self.add_option("-c", "--conf",
            help="config file, ZIP file or base URL",
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
            help='login with given USERNAME and PASSWORD',
            metavar='USERNAME:PASSWORD',
        )
    
    def parse_args(self):
        self.options, self.args = optparse.OptionParser.parse_args(self)
        if self.options.logfile:
            start_logging(self.options.logfile)
        if self.options.conf is None:
            if not self.conf_optional:
                self.error('Please specify --conf option. See --help for all options.')
            return self.options, self.args
        if self.options.metabook:
            self.metabook = simplejson.loads(open(self.options.metabook, 'rb').read())
        if self.options.login is not None and ':' not in self.options.login:
            self.error('Please specify username and password as USERNAME:PASSWORD.')
        if self.args:
            if self.metabook is None:
                self.metabook = metabook.make_metabook()
            for title in self.args:
                self.metabook['items'].append(metabook.make_article(
                    title=unicode(title, 'utf-8'),
                ))
        self.env = self.makewiki()
        return self.options, self.args
    
    def makewiki(self):
        env = wiki.makewiki(self.options.conf, metabook=self.metabook)
        if self.options.noimages:
            env.images = None
        if self.options.template_blacklist:
            if hasattr(env.wiki, 'setTemplateBlacklist'):
                env.wiki.setTemplateBlacklist(self.options.template_blacklist)
            else:
                log.warn('WikiDB does not support setting a template blacklist')
        if self.options.login:
            username, password = self.options.login.split(':', 1)
            if hasattr(env.wiki, 'login'):
                env.wiki.login(username, password)
            else:
                log.warn('WikiDB does not support logging in')
            if env.images and hasattr(env.images, 'login'):
                env.images.login(username, password)
        if self.options.collectionpage:
            wikitext = env.wiki.getRawArticle(self.options.collectionpage)
            if wikitext is None:
                raise RuntimeError('No such collection page: %r' % (
                    self.options.collectionpage,
                ))
            self.metabook = metabook.parse_collection_page(wikitext)
        return env
    
