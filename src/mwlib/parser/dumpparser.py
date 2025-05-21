import os
import re

try:
    from xml.etree import cElementTree
except ImportError:
    import cElementTree

WIKI_NS = "{http://www.mediawiki.org/xml/export-0.3/}"


class Tags:
    # <namespaces><namespace> inside <siteinfo>
    namespace = WIKI_NS + "namespaces/" + WIKI_NS + "namespace"

    page = WIKI_NS + "page"

    # <title> inside <page>
    title = WIKI_NS + "title"

    # <revision> inside <page>
    revision = WIKI_NS + "revision"

    # <id> inside <revision>
    revid = WIKI_NS + "id"

    # <contributor><username> inside <revision>
    username = WIKI_NS + "contributor/" + WIKI_NS + "username"

    # <text> inside <revision>
    text = WIKI_NS + "text"

    # <timestamp> inside <revision>
    timestamp = WIKI_NS + "timestamp"

    # <revision><text> inside <page>
    revision_text = WIKI_NS + "revision/" + WIKI_NS + "text"

    siteinfo = WIKI_NS + "siteinfo"


class Page:
    __slots__ = [
        "title",
        "pageid",
        "namespace_text",
        "namespace",
        "revid",
        "timestamp",
        "username",
        "userid",
        "minor",
        "comment",
        "text",
    ]

    redirect_rex = re.compile(
        r"^#Redirect:?\s*?\[\[(?P<redirect>.*?)\]\]", re.IGNORECASE
    )

    @property
    def redirect(self):
        search = self.redirect_rex.search(self.text)
        if search:
            return search.group("redirect").split("|", 1)[0]
        return None

    def __repr__(self):
        text = repr(self.text[:50])
        redir = self.redirect
        if redir:
            text = f"Redirect to {redir}"
        return f"Page({repr(self.title)} (@{self.timestamp}): {text})"


class DumpParser:
    tags = Tags()

    def __init__(self, xml_filename, ignore_redirects=False):
        self.xml_filename = xml_filename
        self.ignore_redirects = ignore_redirects
        self.title = None
        self.pageid = None

    def open_input_stream(self):
        if self.xml_filename.lower().endswith(".bz2"):
            xml_file = os.popen("bunzip2 -c %s" % self.xml_filename, "r")
        elif self.xml_filename.lower().endswith(".7z"):
            xml_file = os.popen("7z -so x %s" % self.xml_filename, "r")
        else:
            xml_file = open(self.xml_filename)  # noqa: SIM115

        return xml_file

    @staticmethod
    def get_tag(elem):
        # rough is good enough
        return elem.tag[elem.tag.rindex("}") + 1:]

    def __iter__(self):
        xml_file = self.open_input_stream()

        elem_iter = (el for _, el in cElementTree.iterparse(xml_file))
        for elem in elem_iter:
            if self.get_tag(elem) == "page":
                page = self.handle_page_element(elem)
                if page:
                    yield page
                elem.clear()
            elif self.get_tag(elem) == "siteinfo":
                elem.clear()

        xml_file.close()

    def handle_page_element(self, page_elem):
        res = Page()
        last_revision = None
        for element in page_elem:
            tag = self.get_tag(element)
            if tag == "title":
                title = str(element.text)
                res.title = title
            elif tag == "id":
                res.pageid = int(element.text)
            elif tag == "revision":
                last_revision = element

        if last_revision:
            self.handle_revision_element(last_revision, res)

        if self.ignore_redirects and res.redirect:
            return None

        return res

    def handle_revision_element(self, rev_element, res):
        for element in rev_element:
            tag = self.get_tag(element)
            if tag == "id":
                res.revid = int(element.text)
            elif tag == "timestamp":
                res.timestamp = element.text
            elif tag == "minor":
                res.minor = True
            elif tag == "comment":
                res.comment = str(element.text)
            elif tag == "text":
                res.text = str(element.text)
                element.clear()

        return res
