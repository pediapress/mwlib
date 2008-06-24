import optparse

from mwlib.utils import start_logging
from mwlib import wiki, metabook

class OptionParser(optparse.OptionParser):
    def __init__(self, usage=None):
        if usage is None:
            usage = '%prog [OPTIONS] [ARTICLETITLE...]'
        optparse.OptionParser.__init__(self, usage=usage)
        self.metabook = None
        self.add_option("-c", "--conf", help="config file, ZIP file or base URL")
        self.add_option("-m", "--metabook", help="JSON encoded text file with article collection")
        self.add_option('--collectionpage', help='Title of a collection page')
        self.add_option("-x", "--noimages", action="store_true", help="exclude images")
        self.add_option("-l", "--logfile", help="log to logfile")
        self.add_option("--template-blacklist", help="Title of article containing blacklisted templates")
    
    def parse_args(self):
        self.options, self.args = optparse.OptionParser.parse_args(self)
        if self.options.logfile:
            start_logging(self.options.logfile)
        self.metabook = self.get_metabook()
        if self.args:
            self.metabook.addArticles([unicode(x, 'utf-8') for x in self.args])
        self.env = self.makewiki()
        return self.options, self.args
    
    def get_metabook(self):
        mb = metabook.MetaBook()
        if self.options.metabook:
            mb.readJsonFile(self.options.metabook)
        return mb
    
    def makewiki(self):
        env = wiki.makewiki(self.options.conf, metabook=self.metabook)
        if self.options.noimages:
            env.images = None
        if self.options.template_blacklist and hasattr(env.wiki, 'setTemplateBlacklist'):
            # FIXME!
            env.wiki.setTemplateBlacklist(self.options.template_blacklist)
        if self.options.collectionpage:
            self.metabook.loadCollectionPage(env.wiki.getRawArticle(self.options.collectionpage))
        return env
    
