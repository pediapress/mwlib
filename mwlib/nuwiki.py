
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

import os
import zipfile
import shutil
import tempfile
import urllib
import sqlite3dbm
from mwlib import myjson as json

from mwlib import nshandling, utils
from mwlib.log import Log

log = Log('nuwiki')


class page(object):
    def __init__(self, meta, rawtext):
        self.__dict__.update(meta)
        self.rawtext = rawtext

class DumbJsonDB(object):

    def __init__(self, fn, allow_pickle=False):
        self.fn = fn
        self.allow_pickle = allow_pickle
        self.read_db()

    def read_db(self):
        self.db = sqlite3dbm.open(self.fn)

    def __getitem__(self, key):
        v = self.db.get(key, '')
        if v:
            return json.loads(v)
        else:
            return None

    def get(self, key, default=None):
        res = self[key]
        if res == None:
            return default
        else:
            return res

    def items(self):
        return self.db.items()

    def __getstate__(self):
        # FIXME: pickling zip based containers not supported and currently not needed.
        # if desired the content of the db file need to be persisted...
        assert self.allow_pickle, 'ERROR: pickling not allowed for zip files. Use unzipped zip file instead'
        d = self.__dict__.copy()
        del d['db']
        return d

    def __setstate__(self, d):
        self.__dict__ = d
        self.read_db()



class nuwiki(object):
    def __init__(self, path, allow_pickle=False):
        self.path = os.path.abspath(path)
        d = os.path.join(self.path, "images", "safe")
        if not os.path.exists(d):
            try:
                os.makedirs(d)
            except OSError, exc:
                if exc.errno != 17: # file exists
                    raise
            
        self.excluded = set(x.get("title") for x in self._loadjson("excluded.json", []))            

        self.revisions = {}
        self._read_revisions()

        fn = os.path.join(self.path, 'authors.db')
        if not os.path.exists(fn):
            self.authors = None
            log.warn('no authors present. parsing revision info instead')
        else:
            self.authors = DumbJsonDB(fn, allow_pickle=allow_pickle)

        fn = os.path.join(self.path, 'html.db')
        if not os.path.exists(fn):
            self.html = self.extractHTML(self._loadjson("parsed_html.json", {}))
            log.warn('no html present. parsing revision info instead')
        else:
            self.html = DumbJsonDB(fn, allow_pickle=allow_pickle)

        fn = os.path.join(self.path, 'imageinfo.db')
        if not os.path.exists(fn):
            self.imageinfo = self._loadjson("imageinfo.json", {})
            log.warn('loading imageinfo from pickle')
        else:
            self.imageinfo = DumbJsonDB(fn, allow_pickle=allow_pickle)

        self.redirects = self._loadjson("redirects.json", {})
        self.siteinfo = self._loadjson("siteinfo.json", {})
        self.nshandler = nshandling.nshandler(self.siteinfo)        
        self.en_nshandler = nshandling.get_nshandler_for_lang('en') 
        self.nfo = self._loadjson("nfo.json", {})

        self.set_make_print_template()

    def __getstate__(self):
        d = self.__dict__.copy()
        del d['make_print_template']
        return d

    def __setstate__(self, d):
        self.__dict__ = d
        self.set_make_print_template()

    def set_make_print_template(self):
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
        count = 1
        while 1:
            fn = self._pathjoin("revisions-%s.txt" % count)
            if not os.path.exists(fn):
                break
            count += 1
            print "reading", fn
            d=unicode(open(self._pathjoin(fn), "rb").read(), "utf-8")
            pages = d.split("\n --page-- ")

            for p in pages[1:]:
                jmeta, rawtext = p.split("\n", 1)
                meta = json.loads(jmeta)
                pg = Page(meta, rawtext)
                if pg.title in self.excluded and pg.ns!=0:
                    pg.rawtext = unichr(0xebad)
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
    
    def _get_page(self, name, revision=None):
        if revision is not None and name not in self.redirects:
            try:
                page = self.revisions.get(int(revision))
            except TypeError:
                print "Warning: non-integer revision %r" % revision
            else:
                if page and page.rawtext:
                    redirect = self.nshandler.redirect_matcher(page.rawtext)
                    if redirect:
                        return self.get_page(self.nshandler.get_fqname(redirect))
                return page
        
        name = self.redirects.get(name, name)
        
        if self.make_print_template is not None:
            pname = self.make_print_template(name)
            r=self.revisions.get(pname)
            # print "returning print template", repr(pname)
            if r is not None:
                # r.title = name # XXX not so sure about that one???
                return r
            
        return self.revisions.get(name)

    def get_page(self, name, revision=None):
        retval = self._get_page(name,revision=revision)
        # if retval is None:
        #     log.warning("missing page %r" % ((name,revision),))
        return retval
    
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
            fqname = 'File:' + partial # Fallback to default language english
            p = self._pathjoin("images", utils.fsescape(fqname))
            if not self._exists(p):
                return None

        if 1:
            from hashlib import md5
            
            hd = md5(fqname.encode("utf-8")).hexdigest()
            ext = os.path.splitext(p)[-1]
            ext = ext.replace(' ', '')
            # mediawiki gives us png's for these extensions. let's change them here.
            if ext.lower() in (".gif", ".svg", '.tif', '.tiff'):
                # print "change xt:", ext
                ext = ".png"
            hd += ext
                
            safe_path = self._pathjoin("images", "safe", hd)
            if not os.path.exists(safe_path):
                try:
                    os.symlink(os.path.join("..", utils.fsescape(fqname)), safe_path)
                except OSError, exc:
                    if exc.errno != 17: # File exists
                        raise
            return safe_path
        return p

    def get_data(self, name):
        return self._loadjson(name+".json")

    def articles(self):
        res = list(set([p.title for p in self.revisions.values() if p.ns==0]))
        res.sort()
        return res

    def select(self, start, end):
        res = set()
        for p in self.revisions.values():
            if start <= p.title <= end:
                res.add(p.title)
        res = list(res)
        res.sort()
        return res

    def extractHTML(self, parsed_html):
        html = {}
        for article in parsed_html:
            _id = article.get('page') or article.get('oldid')
            html[_id] = article
        return html

NuWiki = nuwiki
Page = page

def extract_member(zipfile, member, dstdir):
    """Copied and adjusted from Python 2.6 stdlib zipfile.py module.

       Extract the ZipInfo object 'member' to a physical
       file on the path targetpath.
    """

    assert dstdir.endswith(os.path.sep), "/ missing at end"
    
    fn = member.filename
    if isinstance(fn, str):
        fn = unicode(fn, 'utf-8')
    targetpath = os.path.normpath(os.path.join(dstdir, fn))
    
    if not targetpath.startswith(dstdir):
        raise RuntimeError("bad filename in zipfile %r" % (targetpath, ))
        
    # Create all upper directories if necessary.
    if member.filename.endswith("/"):
        upperdirs = targetpath
    else:
        upperdirs = os.path.dirname(targetpath)
        
    if not os.path.isdir(upperdirs):
        os.makedirs(upperdirs)

    if not member.filename.endswith("/"):
        open(targetpath, 'wb').write(zipfile.read(member.filename))

def extractall(zf, dst):
    dst = os.path.normpath(os.path.abspath(dst))+os.path.sep
    
    for zipinfo in zf.infolist():
        extract_member(zf, zipinfo, dst)
    
       
class adapt(object):
    edits = None
    interwikimap = None
    was_tmpdir = False
    
    def __init__(self, path_or_instance):
        if isinstance(path_or_instance, zipfile.ZipFile):
            zf = path_or_instance
            tmpdir = tempfile.mkdtemp()
            extractall(zf, tmpdir)
            path_or_instance = tmpdir
            self.was_tmpdir = True
            
        if isinstance(path_or_instance, basestring):
            self.nuwiki = NuWiki(path_or_instance, allow_pickle=not self.was_tmpdir)
        else:
            self.nuwiki = path_or_instance
        self.siteinfo = self.nuwiki.get_siteinfo()
        self.metabook = self.nuwiki.get_data("metabook")
        
    def __getattr__(self, name):
        try:
            return getattr(self.nuwiki, name)
        except AttributeError:
            raise AttributeError()

    def __getstate__(self):
        return self.__dict__

    def __setstate__(self, d):
        self.__dict__ = d

    def getURL(self, name, revision=None, defaultns=nshandling.NS_MAIN):
        base_url = self.nfo["base_url"]
        if not base_url.endswith("/"):
            base_url += "/"
        script_extension = self.nfo.get("script_extension") or ".php"


        p = '%sindex%s?' % (base_url, script_extension)
        if revision is not None:
            return p + 'oldid=%s' % revision
        else:
            fqtitle = self.nshandler.get_fqname(name, defaultns=defaultns)
            return p + 'title=%s' % urllib.quote(fqtitle.replace(' ', '_').encode('utf-8'), safe=':/@')
    
    def getDescriptionURL(self, name):
        return self.getURL(name, defaultns=nshandling.NS_FILE)

    def getAuthors(self, title, revision=None):
        fqname = self.nshandler.get_fqname(title)
        fqname = self.redirects.get(fqname, fqname)

        if getattr(self.nuwiki, 'authors', None) is not None:
            authors = self.nuwiki.authors[fqname]
            return authors
        else:
            from mwlib.authors import get_authors
            if self.edits is None:
                edits = self.edits = {}
                for edit in self.nuwiki.get_data("edits") or []:
                    try:
                        edits[edit['title']] = edit.get("revisions")
                    except KeyError:
                        continue

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

    def getHTML(self, title, revision=None):
        if revision:
            return self.nuwiki.html.get(revision, {})
        else:
            return self.nuwiki.html.get(title, {})

    def getParsedArticle(self, title, revision=None):
        if revision:
            page = self.nuwiki.get_page(None, revision)
        else:
            page = self.normalize_and_get_page(title, 0)

        if page:
            raw = page.rawtext
        else:
            raw = None
            
            
        if raw is None:
            return None

        from mwlib import uparser        

        return uparser.parseString(title=title, raw=raw, wikidb=self, lang=self.siteinfo["general"]["lang"])

    def getLicenses(self):
        from mwlib import metabook
        licenses = self.nuwiki.get_data('licenses') or []
        res = []
        for x in licenses:
            if isinstance(x, dict):
                res.append(metabook.license(title=x["title"], wikitext=x["wikitext"],  _wiki=self))
            elif isinstance(x, metabook.license):
                res.append(x)
                x._wiki = self
        return res
    
    def clear(self):
        if self.was_tmpdir and os.path.exists(self.nuwiki.path):
            print 'removing %r' % self.nuwiki.path
            shutil.rmtree(self.nuwiki.path, ignore_errors=True)
    
    def getDiskPath(self, name, size=None):
        return self.nuwiki.normalize_and_get_image_path(name)

    def get_image_description_page(self, name):
        ns, partial, fqname = self.nshandler.splitname(name, nshandling.NS_FILE)
        page = self.get_page(fqname)
        if page is not None:
            return page
        fqname = self.en_nshandler.get_fqname(partial, nshandling.NS_FILE)
        return self.get_page(fqname)

    def getImageTemplates(self, name, wikidb=None):
        from mwlib.expander import get_templates

        page = self.get_image_description_page(name)
        if page is not None:
            return get_templates(page.rawtext)
        print 'no such image: %r' % name
        return []

    def getImageTemplatesAndArgs(self, name, wikidb=None):
        from mwlib.expander import get_templates, get_template_args
        page = self.get_image_description_page(name)
        if page is not None:
            templates = get_templates(page.rawtext)
            from mwlib.expander import find_template
            from mwlib.templ.evaluate import Expander
            from mwlib.templ.parser import parse
            from mwlib.templ.misc import DictDB
            args = set()
            e=Expander('', wikidb=DictDB())
            # avoid parsing with every call to find_template
            parsed_raw=[parse(page.rawtext, replace_tags=e.replace_tags)]
            for t in templates:
                tmpl = find_template(None, t, parsed_raw[:])
                arg_list = tmpl[1]
                for arg in arg_list:
                    if isinstance(arg, basestring) and len(arg) > 3 and ' ' not in arg:
                        args.add(arg)
            templates.update(args)
            return templates
        return []


    def getImageWords(self, name, wikidb=None):
        import re
        page = self.get_image_description_page(name)
        if page is not None:
            words = re.split('\{|\}|\[|\]| |\,|\|', page.rawtext)
            return list(set([w.lower() for w in  words if w]))
        print 'no such image: %r' % name
        return []



    def getContributors(self, name, wikidb=None):
        page = self.get_image_description_page(name)
        if page is None:
            return []
        users = getContributorsFromInformationTemplate(page.rawtext, page.title, self)
        if users:
            return users
        return self.getAuthors(page.title)


def getContributorsFromInformationTemplate(raw, title, wikidb):
    from mwlib.expander import find_template, get_templates, get_template_args, Expander
    from mwlib import uparser, parser, advtree
    from mwlib.templ.parser import parse
    
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
            # userlinks = getUserLinks(author_arg)
            # if userlinks:
            #     return userlinks
            node = uparser.parseString('', raw=args['Author'], wikidb=wikidb)
            advtree.extendClasses(node)
            txt = node.getAllDisplayText().strip()
            if txt:
                return [txt]

        if args.args:
            return getUserLinks('\n'.join([args.get(i, u'') for i in range(len(args.args))]))

        return []

    expander = Expander(u'', title, wikidb)
    parsed_raw = [parse(raw, replace_tags=expander.replace_tags)]
    template = find_template(None, 'Information', parsed_raw[:])
    if template is not None:
        authors = get_authors_from_template_args(template)
        if authors:
            return authors
    authors = []
    for template in get_templates(raw):
        t = find_template(None, template, parsed_raw[:])
        if t is not None:
            authors.extend(get_authors_from_template_args(t))
    if authors:
        return authors
    return getUserLinks(raw)
