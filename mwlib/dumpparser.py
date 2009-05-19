import os
import re

try:
    from xml.etree import cElementTree
except ImportError:
    import cElementTree

ns = '{http://www.mediawiki.org/xml/export-0.3/}'
class Tags:

    # <namespaces><namespace> inside <siteinfo>
    namespace = ns + 'namespaces/' + ns + 'namespace'

    page = ns + 'page'

    # <title> inside <page>
    title = ns + 'title'

    # <revision> inside <page>
    revision = ns + 'revision'

    # <id> inside <revision>
    revid = ns + 'id'

    # <contributor><username> inside <revision>
    username = ns + 'contributor/' + ns + 'username'

    # <text> inside <revision>
    text = ns + 'text'

    # <timestamp> inside <revision>
    timestamp = ns + 'timestamp'

    # <revision><text> inside <page>
    revision_text = ns + 'revision/' + ns + 'text'

    siteinfo = ns + "siteinfo"


class Page(object):
    __slots__ = [
        'title', 'pageid', 'namespace_text',
        'namespace',
        'revid', 'timestamp',
        'username', 'userid',
        'minor', 'comment', 'text'
    ]


    redirect_rex = re.compile(r'^#Redirect:?\s*?\[\[(?P<redirect>.*?)\]\]', re.IGNORECASE)

    @property
    def redirect(self):
        mo = self.redirect_rex.search(self.text)
        if mo:
            return mo.group('redirect').split("|", 1)[0]
        return None

    def __repr__(self):
        text = repr(self.text[:50])
        redir = self.redirect
        if redir:
            text = "Redirect to %s" % repr(redir)
        return 'Page(%s (@%s): %s)' % (repr(self.title), self.timestamp, text)


class DumpParser(object):

    tags = Tags()

    def __init__(self, xmlfilename,
                 ignore_redirects=False):
        self.xmlfilename = xmlfilename
        self.ignore_redirects = ignore_redirects

    def openInputStream(self):
        if self.xmlfilename.lower().endswith(".bz2"):
            f = os.popen("bunzip2 -c %s" % self.xmlfilename, "r")
        elif self.xmlfilename.lower().endswith(".7z"):
            f = os.popen("7z -so x %s" % self.xmlfilename, "r")
        else:
            f = open(self.xmlfilename, "r")        

        return f

    @staticmethod
    def getTag(elem):
        # rough is good enough
        return elem.tag[elem.tag.rindex('}')+1:]

    def handleSiteinfo(self, siteinfo):
        pass
    
        # for nsElem in siteinfo.findall(self.tags.namespace):
        #     try:
        #         self.namespaces[nsElem.text.lower()] = int(nsElem.get('key'))
        #     except AttributeError:
        #         # text is probably None
        #         pass
        
    def __iter__(self):
        f = self.openInputStream()    
        
        elemIter = (el for evt, el in cElementTree.iterparse(f))
        for elem in elemIter:
            if self.getTag(elem) == 'page':
                page = self.handlePageElement(elem)
                if page:
                    yield page
                elem.clear()
            elif self.getTag(elem) == 'siteinfo':
                self.handleSiteinfo(elem)
                elem.clear()
        
        f.close()
    
    def handlePageElement(self, pageElem):
        res = Page()
        lastRevision = None
        for el in pageElem:
            tag = self.getTag(el)
            if tag == 'title':
                title = unicode(el.text)
                res.title = title
            elif tag == 'id':
                res.pageid = int(el.text)
            elif tag == 'revision':
                lastRevision = el

        if lastRevision:
            self.handleRevisionElement(lastRevision, res)

        if self.ignore_redirects and res.redirect:
            return None

        return res

    def handleRevisionElement(self, revElem, res):
        for el in revElem:
            tag = self.getTag(el)
            if tag == 'id':
                res.revid = int(el.text)
            elif tag == 'timestamp':
                res.timestamp = el.text
            elif tag == 'contributor':
                pass
                #res.username, res.userid = self.handleContributorElement(el)
            elif tag == 'minor':
                res.minor = True
            elif tag == 'comment':
                res.comment = unicode(el.text)
            elif tag == 'text':
                res.text = unicode(el.text)
                el.clear()

        return res

    def handleContributorElement(self, conElem):
        username = None
        userid = None
        for el in conElem:
            if self.getTag(el) == 'username':
                username = unicode(el.text)
            elif self.getTag(el) == 'id':
                userid = int(el.text)
        return (username, userid)
