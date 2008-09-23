import urllib

from mwlib import parser, uparser, utils
from mwlib.log import Log

log = Log('wikidbbase')

class WikiDBBase(object):
    """Base class for WikiDBs"""
    
    def getLinkURL(self, link, title, revision=None):
        """Get a full HTTP URL for the given link object, parsed from an article
        in this WikiDB.
        
        @param link: link node from parser
        @type link: L{mwlib.parser.Link}
        
        @param title: title of containing article
        @type title: unicode
        
        @param revision: revision of containing article (optional)
        @type revision: unicode
        
        @returns: full HTTP URL or None if it could not be constructed
        @rtype: str or NoneType
        """
        
        if isinstance(link, parser.ArticleLink)\
            or isinstance(link, parser.CategoryLink)\
            or isinstance(link, parser.NamespaceLink):
            
            target = link.full_target or link.target
            
            if not target:
                return None
            
            if isinstance(link, parser.ArticleLink) and target[0] == '/':
                target = title + target
            
            url = self.getURL(target)
            if url:
                return url
            
            # the following code is kinda hack
            my_url = self.getURL(title, revision=revision)
            if my_url is None:
                return None
            my_title = urllib.quote(title.replace(" ", "_").encode('utf-8'), safe=':/@')
            link_title = urllib.quote(link.full_target.replace(" ", "_").encode('utf-8'), safe=':/@')
            pos = my_url.find(my_title)
            if pos == -1:
                return None
            return my_url[:pos] + link_title
        
        if isinstance(link, parser.LangLink)\
            or isinstance(link, parser.InterwikiLink):
            if not hasattr(self, 'getInterwikiMap'):
                return None
            prefix, target = link.full_target.split(':', 1)
            interwikimap = self.getInterwikiMap(title, revision=revision)
            if interwikimap and prefix in interwikimap:
                url = utils.get_safe_url(interwikimap[prefix]['url'].replace(
                    '$1',
                    urllib.quote(target.encode('utf-8'), safe='/:@'),
                ))
                return url
        
        log.warn('unhandled link in getLinkURL(): %s with (full)target %r' % (
            link.__class__.__name__, getattr(link, 'full_target', None) or link.target,
        ))
        return None

    def getParsedArticle(self, title, revision=None):
        raw = self.getRawArticle(title, revision=revision)
        if raw is None:
            return None
        article = self._getArticle(title, revision=revision)
        lang = None
        source = self.getSource(title, revision=revision)
        if source is not None:
            lang = source.get('language')
        return uparser.parseString(title=title, raw=raw, wikidb=self, lang=lang)
    
