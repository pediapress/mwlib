
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.txt for additional licensing information.

import os
import zipfile
import tempfile
import urllib
try:
    import simplejson as json
except ImportError:
    import json

from mwlib import nshandling, utils
from mwlib.log import Log

log = Log('nuwiki')


class page(object):
    def __init__(self, meta, rawtext):
        self.__dict__.update(meta)
        self.rawtext = rawtext
        
class nuwiki(object):
    def __init__(self, path):
        self.path = os.path.abspath(path)
        d = os.path.join(self.path, "images", "safe")
        if not os.path.exists(d):
            os.makedirs(d)
            
        self.excluded = set(x.get("title") for x in self._loadjson("excluded.json", []))            
        
        self.revisions = {}
        self._read_revisions()
        
        self.redirects = self._loadjson("redirects.json", {})
        self.siteinfo = self._loadjson("siteinfo.json", {})
        self.nshandler = nshandling.nshandler(self.siteinfo)        
        self.nfo = self._loadjson("nfo.json", {})
        p = self.nfo.get("print_template_pattern")
        if p and "$1" in p:
            self.make_print_template = utils.get_print_template_maker(p)
        else:
            self.make_print_template = None
            
    def _loadjson(self, path, default=None):
        path = self._pathjoin(path)
        if self._exists(path):
            return json.load(open(path, "rb"))
        return default
        
    def _read_revisions(self):
        d=unicode(open(self._pathjoin("revisions-1.txt"), "rb").read(), "utf-8")
        pages = d.split("\n --page-- ")

        for p in pages[1:]:
            jmeta, rawtext = p.split("\n", 1)
            meta = json.loads(jmeta)
            pg = page(meta, rawtext)
            if pg.title not in self.excluded:
                revid = meta.get("revid")
                if revid is None:
                    self.revisions[pg.title] = pg
                    continue

                self.revisions[meta["revid"]] = pg
            # else:
            #     print "excluding:", repr(pg.title)
                
        tmp = self.revisions.items()
        tmp.sort(reverse=True)
        for revid, p in tmp:
            title = p.title
            if title not in self.revisions:
                self.revisions[title] = p
                
    def _pathjoin(self, *p):
        return os.path.join(self.path, *p)
    
    def _exists(self, p):
        return os.path.exists(p)
    
    def get_siteinfo(self):
        return self.siteinfo
    
    def get_page(self, name, revision=None):
        if revision is not None:
            try:
                return self.revisions.get(int(revision))
            except TypeError:
                print "Warning: non-integer revision %r" % revision
        
        name = self.redirects.get(name, name)
        
        if self.make_print_template is not None:
            pname = self.make_print_template(name)
            r=self.revisions.get(pname)
            # print "returning print template", repr(pname)
            if r is not None:
                # r.title = name # XXX not so sure about that one???
                return r
            
        return self.revisions.get(name)
    
    def normalize_and_get_page(self, name, defaultns):
        fqname = self.nshandler.get_fqname(name, defaultns=defaultns)
        return self.get_page(fqname)

    def normalize_and_get_image_path(self, name):
        assert isinstance(name, basestring)
        name = unicode(name)
        
        ns, partial, fqname = self.nshandler.splitname(name, defaultns=6)
        if ns != 6:
            return
        
        if "/" in fqname:
            return None
        
        
        
        
        p = self._pathjoin("images", utils.fsescape(fqname))
        if not self._exists(p):
            return None

        if 1:
            try:
                from hashlib import md5
            except ImportError:
                from md5 import md5
            
            hd = md5(fqname.encode("utf-8")).hexdigest()
            ext = os.path.splitext(p)[-1]
            
            # mediawiki gives us png's for these extensions. let's change them here.
            if ext.lower() in (".gif", ".svg"):
                # print "change xt:", ext
                ext = ".png"
            hd += ext
                
            safe_path = self._pathjoin("images", "safe", hd)
            if not os.path.exists(safe_path):
                os.symlink(os.path.join("..", utils.fsescape(fqname)), safe_path)
            return safe_path
        
        return p

    def get_data(self, name):
        return self._loadjson(name+".json")
    
    
def extract_member(zipfile, member, targetpath):
    """Copied and adjusted from Python 2.6 stdlib zipfile.py module.

       Extract the ZipInfo object 'member' to a physical
       file on the path targetpath.
    """

    # build the destination pathname, replacing
    # forward slashes to platform specific separators.
    if targetpath[-1:] in (os.path.sep, os.path.altsep):
        targetpath = targetpath[:-1]

    # don't include leading "/" from file name if present
    if member.filename[0] == '/':
        targetpath = os.path.join(targetpath, member.filename[1:])
    else:
        targetpath = os.path.join(targetpath, member.filename)

    targetpath = os.path.normpath(targetpath)

    # Create all upper directories if necessary.
    upperdirs = os.path.dirname(targetpath)
    if upperdirs and not os.path.exists(upperdirs):
        os.makedirs(upperdirs)

    if member.filename[-1] == '/':
        os.mkdir(targetpath)
    else:
        open(targetpath, 'wb').write(zipfile.read(member.filename))

class Adapt(object):
    edits = None
    interwikimap = None
    
    def __init__(self, path_or_instance):
        if isinstance(path_or_instance, zipfile.ZipFile):
            zf = path_or_instance
            tmpdir = tempfile.mkdtemp()
            if hasattr(zf, 'extractall'):
                zf.extractall(tmpdir) # only available in Python >= 2.6
            else:
                for zipinfo in zf.infolist():
                    extract_member(zf, zipinfo, tmpdir)

            path_or_instance = tmpdir
            
                
        if isinstance(path_or_instance, basestring):
            self.nuwiki = nuwiki(path_or_instance)
        else:
            self.nuwiki = path_or_instance
        self.siteinfo = self.nuwiki.get_siteinfo()
        self.metabook = self.nuwiki.get_data("metabook")
        
    def __getattr__(self, name):
        try:
            return getattr(self.nuwiki, name)
        except AttributeError:
            raise AttributeError()
    
        
    def getTemplate(self, title, followRedirects=True):
        p = self.nuwiki.normalize_and_get_page(title, defaultns=10)
        if p:
            return p.rawtext
            
    def getRawArticle(self, title, revision=None):
        if revision is not None:
            p = self.nuwiki.get_page(None, revision)
        else:
            p = self.nuwiki.normalize_and_get_page(title, defaultns=0)
            
        if p:
            return p.rawtext
        
    def getURL(self, name, revision=None, defaultns=nshandling.NS_MAIN):
        p = '%(base_url)sindex%(script_extension)s?' % self.nfo
        if revision is not None:
            return p + 'oldid=%s' % revision
        else:
            fqtitle = self.nshandler.get_fqname(name, defaultns=defaultns)
            return p + 'title=%s' % urllib.quote(fqtitle.replace(' ', '_').encode('utf-8'), safe=':/@')
    
    def getDescriptionURL(self, name):
        return self.getURL(name, defaultns=nshandling.NS_FILE)

    def getAuthors(self, title, revision=None):
        from mwlib.authors import get_authors
        
        if self.edits is None:
            edits = self.edits = {}
            for edit in self.nuwiki.get_data("edits") or []:
                try:
                    edits[edit['title']] = edit.get("revisions")
                except KeyError:
                    continue

        fqname = self.nshandler.get_fqname(title)
        revisions = self.edits.get(fqname, [])
        authors = get_authors(revisions)
        return authors
    
    def getSource(self, title, revision=None):
        from mwlib.metabook import make_source

        g = self.siteinfo['general']
        return make_source(
            name='%s (%s)' % (g['sitename'], g['lang']),
            url=g['base'],
            language=g['lang'],
            base_url=self.nfo['base_url'],
            script_extension=self.nfo['script_extension'],
        )

    def getParsedArticle(self, title, revision=None):
        raw = self.getRawArticle(title, revision=revision)
        if raw is None:
            return None

        from mwlib import uparser        

        return uparser.parseString(title=title, raw=raw, wikidb=self, lang=self.siteinfo["general"]["lang"])

    def getLicenses(self):
        return self.nuwiki.get_data('licenses')

    def clear(self):
        pass
    
    def getDiskPath(self, name, size=None):
        return self.nuwiki.normalize_and_get_image_path(name)

    def getImageTemplates(self, name, wikidb=None):
        from mwlib.expander import get_templates

        fqname = self.nshandler.get_fqname(name, 6)
        page = self.get_page(fqname)
        if page is not None:
            return get_templates(page.rawtext)
        print 'no such image: %r' % fqname
        return []

    def getContributors(self, name, wikidb=None):
        fqname = self.nshandler.get_fqname(name, 6)

        page = self.get_page(fqname)
        if page is not None:
            users = getContributorsFromInformationTemplate(page.rawtext, fqname, self)
            if users:
                return users

        return self.getAuthors(fqname)



def getContributorsFromInformationTemplate(raw, title, wikidb):
    from mwlib.expander import find_template, get_templates, get_template_args, Expander
    from mwlib import uparser, parser, advtree
    
    def getUserLinks(raw):
        def isUserLink(node):
            return isinstance(node, parser.NamespaceLink) and node.namespace == 2 # NS_USER

        result = list(set([
            u.target
            for u in uparser.parseString(title,
                raw=raw,
                wikidb=wikidb,
            ).filter(isUserLink)
        ]))
        result.sort()
        return result

    def get_authors_from_template_args(template):
        args = get_template_args(template, expander)

        author_arg = args.get('Author', None)
        if author_arg:
            userlinks = getUserLinks(author_arg)
            if userlinks:
                return userlinks
            node = uparser.parseString('', raw=args['Author'], wikidb=wikidb)
            advtree.extendClasses(node)
            return [node.getAllDisplayText()]

        if args.args:
            return getUserLinks('\n'.join([args.get(i, u'') for i in range(len(args.args))]))
        
        return []

    expander = Expander(u'', title, wikidb)       

    template = find_template(raw, 'Information')
    if template is not None:
        authors = get_authors_from_template_args(template)
        if authors:
            return authors

    authors = []
    for template in get_templates(raw):
        t = find_template(raw, template)
        if t is not None:
            authors.extend(get_authors_from_template_args(t))
    if authors:
        return authors

    return getUserLinks(raw)
