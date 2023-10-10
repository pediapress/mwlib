# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

import os
import shutil
import tempfile
import zipfile
from hashlib import sha256

import six
import six.moves.urllib.error
import six.moves.urllib.parse
import six.moves.urllib.request
from six import unichr
from sqlitedict import SqliteDict

from mwlib import metabook, nshandling, parser
from mwlib.expander import Expander, find_template, get_template_args, get_templates
from mwlib.refine import uparser
from mwlib.templ.parser import parse
from mwlib.tree import advtree
from mwlib.utilities import myjson as json
from mwlib.utilities import utils
from mwlib.utilities.log import Log
from mwlib.utilities.utils import python2sort

log = Log("nuwiki")


class Page:
    expanded = 0

    def __init__(self, meta, rawtext):
        self.__dict__.update(meta)
        self.rawtext = rawtext


class DumbJsonDB:
    database = None

    def __init__(self, file_name, allow_pickle=False):
        self.file_name = file_name
        self.allow_pickle = allow_pickle
        self.read_db()

    def read_db(self):
        self.database = SqliteDict(self.file_name)

    def __getitem__(self, key):
        val = self.database.get(key, "")
        if val:
            return json.loads(val)
        else:
            return None

    def get(self, key, default=None):
        res = self[key]
        if res is None:
            return default
        else:
            return res

    def items(self):
        return list(self.database.items())

    def __getstate__(self):
        # FIXME: pickling zip based containers not supported
        # and currently not needed.
        # if desired the content of the database file need to be persisted...
        if not self.allow_pickle:
            raise ValueError(
                "ERROR: pickling not allowed for zip files. Use unzipped zip file instead"
            )
        data = self.__dict__.copy()
        del data["db"]
        return data

    def __setstate__(self, data):
        self.__dict__ = data
        self.read_db()


class NuWiki:
    def __init__(self, path, allow_pickle=False):
        self.path = os.path.abspath(path)
        directory_path = os.path.join(self.path, "images", "safe")
        if not os.path.exists(directory_path):
            try:
                os.makedirs(directory_path)
            except OSError as exc:
                if exc.errno != 17:  # file exists
                    raise

        self.excluded = {x.get("title") for x in self._loadjson("excluded.json", [])}

        self.revisions = {}
        self._read_revisions()

        file_name = os.path.join(self.path, "authors.db")
        if not os.path.exists(file_name):
            self.authors = None
            log.warn("no authors present. parsing revision info instead")
        else:
            self.authors = DumbJsonDB(file_name, allow_pickle=allow_pickle)

        file_name = os.path.join(self.path, "html.db")
        if not os.path.exists(file_name):
            self.html = self.extract_html(self._loadjson("parsed_html.json", {}))
            log.warn("no html present. parsing revision info instead")
        else:
            self.html = DumbJsonDB(file_name, allow_pickle=allow_pickle)

        file_name = os.path.join(self.path, "imageinfo.db")
        if not os.path.exists(file_name):
            self.imageinfo = self._loadjson("imageinfo.json", {})
            log.warn("loading imageinfo from pickle")
        else:
            self.imageinfo = DumbJsonDB(file_name, allow_pickle=allow_pickle)

        self.redirects = self._loadjson("redirects.json", {})
        self.siteinfo = self._loadjson("siteinfo.json", {})
        self.nshandler = nshandling.NsHandler(self.siteinfo)
        self.en_nshandler = nshandling.get_nshandler_for_lang("en")
        self.nfo = self._loadjson("nfo.json", {})

        self.set_make_print_template()

    def __getstate__(self):
        data = self.__dict__.copy()
        del data["make_print_template"]
        return data

    def __setstate__(self, data):
        self.__dict__ = data
        self.set_make_print_template()

    def set_make_print_template(self):
        self.make_print_template = None

    def _loadjson(self, path, default=None):
        path = self._pathjoin(path)
        if self._exists(path):
            return json.load(open(path, "rb"))
        return default

    def _read_revisions(self):
        count = 1
        while True:
            file_name = self._pathjoin("revisions-%s.txt" % count)
            if not os.path.exists(file_name):
                break
            count += 1
            print("reading", file_name)
            file_content = six.text_type(open(self._pathjoin(file_name), "rb").read(), "utf-8")
            pages = file_content.split("\n --page-- ")

            for page in pages[1:]:
                jmeta, rawtext = page.split("\n", 1)
                meta = json.loads(jmeta)
                new_page = Page(meta, rawtext)
                if new_page.title in self.excluded and new_page.ns != 0:
                    new_page.rawtext = unichr(0xEBAD)
                revid = meta.get("revid")
                if revid is None:
                    self.revisions[new_page.title] = new_page
                    continue

                self.revisions[meta["revid"]] = new_page

        tmp = list(self.revisions.items())
        python2sort(tmp, reverse=True)
        for revid, page in tmp:
            title = page.title
            if title not in self.revisions:
                self.revisions[title] = page

    def _pathjoin(self, *paths):
        return os.path.join(self.path, *paths)

    def _exists(self, path):
        return os.path.exists(path)

    def get_siteinfo(self):
        return self.siteinfo

    def _get_page(self, name, revision=None):
        if revision is not None and name not in self.redirects:
            try:
                page = self.revisions.get(int(revision))
            except TypeError:
                print("Warning: non-integer revision %r" % revision)
            else:
                if page and page.rawtext:
                    redirect = self.nshandler.redirect_matcher(page.rawtext)
                    if redirect:
                        return self.get_page(self.nshandler.get_fqname(redirect))
                return page

        oldname = name
        name = self.redirects.get(name, name)

        return self.revisions.get(name) or self.revisions.get(oldname)

    def get_page(self, name, revision=None):
        retval = self._get_page(name, revision=revision)
        return retval

    def normalize_and_get_page(self, name, defaultns):
        fqname = self.nshandler.get_fqname(name, defaultns=defaultns)
        return self.get_page(fqname)

    def normalize_and_get_image_path(self, name):
        if not isinstance(name, six.string_types):
            raise ValueError("name must be a string")
        name = six.text_type(name)
        namespace, partial, fqname = self.nshandler.splitname(name, defaultns=6)
        if namespace != 6:
            return

        if "/" in fqname:
            return None

        path = self._pathjoin("images", utils.fs_escape(fqname))
        if not self._exists(path):
            fqname = "File:" + partial  # Fallback to default language english
            path = self._pathjoin("images", utils.fs_escape(fqname))
            if not self._exists(path):
                return None

        hex_digest = sha256(fqname.encode("utf-8")).hexdigest()
        ext = os.path.splitext(path)[-1]
        ext = ext.replace(" ", "")
        # mediawiki gives us png's for these extensions. 
        # let's change them here.
        if ext.lower() in (".gif", ".svg", ".tif", ".tiff"):
            ext = ".png"
        hex_digest += ext
        safe_path = self._pathjoin("images", "safe", hex_digest)
        if not os.path.exists(safe_path):
            try:
                os.symlink(os.path.join("..", utils.fs_escape(fqname)),
                           safe_path)
            except OSError as exc:
                if exc.errno != 17:  # File exists
                    raise
        return safe_path

    def get_data(self, name):
        return self._loadjson(name + ".json")

    def articles(self):
        res = sorted({p.title for p in self.revisions.values() if p.ns == 0})
        return res

    def select(self, start, end):
        res = set()
        for paragraph in self.revisions.values():
            if start <= paragraph.title <= end:
                res.add(paragraph.title)
        res = sorted(res)
        return res

    def extract_html(self, parsed_html):
        html = {}
        for article in parsed_html:
            _id = article.get("page") or article.get("oldid")
            html[_id] = article
        return html


def extract_member(zipfile, member, dstdir):
    """Copied and adjusted from Python 2.6 stdlib zipfile.py module.

    Extract the ZipInfo object 'member' to a physical
    file on the path targetpath.
    """
    if not dstdir.endswith(os.path.sep):
        raise ValueError("Bad destination directory: %r - / missing at end" % dstdir)

    file_name = member.filename
    targetpath = os.path.normpath(os.path.join(dstdir, file_name))

    if not targetpath.startswith(dstdir):
        raise RuntimeError("bad filename in zipfile {!r}".format(targetpath))

    # Create all upper directories if necessary.
    upperdirs = (
        targetpath if member.filename.endswith("/") else os.path.dirname(targetpath)
    )

    if not os.path.isdir(upperdirs):
        os.makedirs(upperdirs)

    if not member.filename.endswith("/"):
        open(targetpath, "wb").write(zipfile.read(member.filename))


def extractall(zip_file, dst):
    dst = os.path.normpath(os.path.abspath(dst)) + os.path.sep

    for zipinfo in zip_file.infolist():
        extract_member(zip_file, zipinfo, dst)


class Adapt:
    edits = None
    interwikimap = None
    was_tmpdir = False

    def __init__(self, path_or_instance):
        if isinstance(path_or_instance, zipfile.ZipFile):
            zip_file = path_or_instance
            tmpdir = tempfile.mkdtemp()
            extractall(zip_file, tmpdir)
            path_or_instance = tmpdir
            self.was_tmpdir = True

        if isinstance(path_or_instance, six.string_types):
            self.nuwiki = NuWiki(path_or_instance,
                                 allow_pickle=not self.was_tmpdir)
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

    def __setstate__(self, data):
        self.__dict__ = data

    def get_url(self, name, revision=None, defaultns=nshandling.NS_MAIN):
        base_url = self.nfo["base_url"]
        if not base_url.endswith("/"):
            base_url += "/"
        script_extension = self.nfo.get("script_extension") or ".php"

        index_url_prefix = "%sindex%s?" % (base_url, script_extension)
        if revision is not None:
            return index_url_prefix + "oldid=%s" % revision
        else:
            fqtitle = self.nshandler.get_fqname(name, defaultns=defaultns)
            return index_url_prefix + "title=%s" % six.moves.urllib.parse.quote(
                fqtitle.replace(" ", "_").encode("utf-8"), safe=":/@"
            )

    def get_description_url(self, name):
        return self.get_url(name, defaultns=nshandling.NS_FILE)

    def get_authors(self, title, revision=None):
        fqname = self.nshandler.get_fqname(title)
        if fqname in self.redirects:
            res = self._get_authors(self.redirects.get(fqname, fqname))
        else:
            res = None

        return res if res is not None else self._get_authors(fqname)

    def _get_authors(self, fqname):
        if getattr(self.nuwiki, "authors", None) is not None:
            authors = self.nuwiki.authors[fqname]
            return authors
        else:
            from mwlib.authors import get_authors

            if self.edits is None:
                edits = self.edits = {}
                for edit in self.nuwiki.get_data("edits") or []:
                    try:
                        edits[edit["title"]] = edit.get("revisions")
                    except KeyError:
                        continue

            revisions = self.edits.get(fqname, [])
            authors = get_authors(revisions)

            return authors

    def get_source(self, title, revision=None):

        general_info = self.siteinfo["general"]
        return metabook.Source(
            name="%s (%s)" % (general_info["sitename"], general_info["lang"]),
            url=general_info["base"],
            language=general_info["lang"],
            base_url=self.nfo["base_url"],
            script_extension=self.nfo["script_extension"],
        )

    def get_html(self, title, revision=None):
        if revision:
            return self.nuwiki.html.get(revision, {})
        else:
            return self.nuwiki.html.get(title, {})

    def get_parsed_article(self, title, revision=None):
        if revision:
            page = self.nuwiki.get_page(None, revision)
        else:
            page = self.normalize_and_get_page(title, 0)

        if page:
            raw = page.rawtext
            expand_templates = not page.expanded
        else:
            raw = None
            expand_templates = True

        if raw is None:
            return None

        return uparser.parse_string(
            title=title,
            raw=raw,
            wikidb=self,
            lang=self.siteinfo["general"]["lang"],
            expand_templates=expand_templates,
        )

    def get_licenses(self):
        from mwlib import metabook

        licenses = self.nuwiki.get_data("licenses") or []
        res = []
        for license in licenses:
            if isinstance(license, dict):
                res.append(
                    metabook.License(
                        title=license["title"], wikitext=license["wikitext"], _wiki=self
                    )
                )
            elif isinstance(license, metabook.License):
                res.append(license)
                license._wiki = self
        return res

    def clear(self):
        if self.was_tmpdir and os.path.exists(self.nuwiki.path):
            print("removing %r" % self.nuwiki.path)
            shutil.rmtree(self.nuwiki.path, ignore_errors=True)

    def get_disk_path(self, name, size=None):
        return self.nuwiki.normalize_and_get_image_path(name)

    def get_image_description_page(self, name):
        _, partial, fqname = self.nshandler.splitname(name,
                                                      nshandling.NS_FILE)
        page = self.get_page(fqname)
        if page is not None:
            return page
        fqname = self.en_nshandler.get_fqname(partial, nshandling.NS_FILE)
        return self.get_page(fqname)

    def get_image_templates(self, name, wikidb=None):
        from mwlib.expander import get_templates

        page = self.get_image_description_page(name)
        if page is not None:
            return get_templates(page.rawtext)
        print("no such image: %r" % name)
        return []

    def get_image_templates_and_args(self, name, wikidb=None):
        from mwlib.expander import get_templates

        page = self.get_image_description_page(name)
        if page is not None:
            templates = get_templates(page.rawtext)
            from mwlib.expander import find_template
            from mwlib.templ.evaluate import Expander
            from mwlib.templ.misc import DictDB
            from mwlib.templ.parser import parse

            args = set()
            exp = Expander("", wikidb=DictDB())
            # avoid parsing with every call to find_template
            parsed_raw = [parse(page.rawtext, replace_tags=exp.replace_tags)]
            for template in templates:
                tmpl = find_template(None, template, parsed_raw[:])
                arg_list = tmpl[1]
                for arg in arg_list:
                    if (
                        isinstance(arg, six.string_types)
                        and len(arg) > 3
                        and " " not in arg
                    ):
                        args.add(arg)
            templates.update(args)
            return templates
        return []

    def get_contributors(self, name, wikidb=None):
        page = self.get_image_description_page(name)
        if page is None:
            return []
        users = get_contributors_from_information_template(page.rawtext,
                                                       page.title, self)
        if users:
            return users
        return self.get_authors(page.title)


def get_contributors_from_information_template(raw, title, wikidb):
    def get_user_links(raw):
        def is_user_link(node):
            return (
                isinstance(node, parser.NamespaceLink) and node.namespace == 2
            )  # NS_USER

        result = sorted(
            {
                u.target
                for u in uparser.parse_string(
                    title,
                    raw=raw,
                    wikidb=wikidb,
                ).filter(is_user_link)
            }
        )
        return result

    def get_authors_from_template_args(template):
        args = get_template_args(template, expander)

        author_arg = args.get("Author", None)
        if author_arg:
            node = uparser.parse_string("", raw=args["Author"], wikidb=wikidb)
            advtree.extend_classes(node)
            txt = node.get_all_display_text().strip()
            if txt:
                return [txt]

        if args.args:
            return get_user_links(
                "\n".join([args.get(i, "") for i in range(len(args.args))])
            )

        return []

    expander = Expander("", title, wikidb)
    parsed_raw = [parse(raw, replace_tags=expander.replace_tags)]
    template = find_template(None, "Information", parsed_raw[:])
    if template is not None:
        authors = get_authors_from_template_args(template)
        if authors:
            return authors
    authors = []
    for template in get_templates(raw):
        found_template = find_template(None, template, parsed_raw[:])
        if found_template is not None:
            authors.extend(get_authors_from_template_args(found_template))
    if authors:
        return authors
    return get_user_links(raw)
