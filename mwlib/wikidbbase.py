import urllib

from mwlib import parser, uparser
from mwlib.log import Log

log = Log('wikidbbase')

class WikiDBBase(object):
    """Base class for WikiDBs"""
    
    interwikimap = None
    
    def getLinkURL(self, link):
        """Get a full HTTP URL for the given link object, parsed from an article
        in this WikiDB.
        
        @param link: link node from parser
        @type link: L{mwlib.parser.Link}
        
        @returns: full HTTP URL
        @rtype: str
        """
        
        if isinstance(link, parser.ArticleLink):
            return self.getURL(link.target)
        
        if isinstance(link, parser.CategoryLink)\
            or isinstance(link, parser.NamespaceLink):
            return self.getURL(link.full_target)
        
        if isinstance(link, parser.LangLink)\
            or isinstance(link, parser.InterwikiLink):
            if self.interwikimap is None and hasattr(self, 'getInterwikiMap'):
                self.getInterwikiMap()
            prefix, title = link.full_target.split(':', 1)
            if self.interwikimap and prefix in self.interwikimap:
                return self.interwikimap[prefix]['url'].replace(
                    '$1',
                    urllib.quote(title.encode('utf-8'), safe='/:@'),
                )
        
        log.warn('unhandled link in getLinkURL(): %s with (full)target %r' % (
            link.__class__.__name__, link.full_target or link.target,
        ))
        return None
