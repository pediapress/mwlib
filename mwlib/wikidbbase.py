"""TODO: Get rid of this module"""

from mwlib import uparser

def normalize_title(title):
    if not title:
        return title
    if not isinstance(title, unicode):
        title = unicode(title, 'utf-8')
    title = title.replace('_', ' ')
    title = title[0].upper() + title[1:]
    return title

class WikiDBBase(object):
    """Base class for WikiDBs"""
    
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
    
