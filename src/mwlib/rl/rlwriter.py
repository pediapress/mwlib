#! /usr/bin/env python

# Copyright (c) 2007, PediaPress GmbH
# See README.txt for additional licensing information.

import copy
import gc
import gettext
import os
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
import urllib.error
import urllib.parse
import urllib.request

try:
    from hashlib import md5
except ImportError:
    from md5 import md5

import contextlib
from xml.sax.saxutils import escape as xmlescape

from PIL import Image as PilImage
from pygments import highlight, lexers
from reportlab import rl_config
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.lib.units import cm
from reportlab.platypus.doctemplate import BaseDocTemplate, NextPageTemplate, NotAtTopPageBreak
from reportlab.platypus.flowables import CondPageBreak, HRFlowable, PageBreak, Spacer
from reportlab.platypus.paragraph import Paragraph
from reportlab.platypus.tables import Table
from reportlab.platypus.xpreformatted import XPreformatted

from mwlib import log, parser, timeline, uparser
from mwlib._version import version as mwlibversion
from mwlib.rl._version import version as rlwriterversion
from mwlib.rl.customflowables import (
    DummyTable,
    Figure,
    FiguresAndParagraphs,
    SmartKeepTogether,
    TocEntry,
)
from mwlib.rl.customnodetransformer import CustomNodeTransformer
from mwlib.rl.formatter import RLFormatter
from mwlib.rl.toc import TocRenderer
from mwlib.writer import miscutils, styleutils
from mwlib.writer.imageutils import ImageUtils
from mwlib.writer.licensechecker import LicenseChecker

from . import fontconfig, pdfstyles, rltables
from .pagetemplates import PPDocTemplate, TitlePage, WikiPage
from .pdfstyles import heading_style, print_height, print_width, table_style, text_style
from .rlsourceformatter import ReportlabFormatter

with contextlib.suppress(ImportError):
    from mwlib import _extversion


from mwlib import advtree, writerbase
from mwlib.treecleaner import TreeCleaner

try:
    from mwlib import linuxmem
except ImportError:
    linuxmem = None


def _check_reportlab():
    from reportlab.pdfbase.pdfdoc import PDFDictionary

    try:
        PDFDictionary.__getitem__
    except AttributeError:
        raise ImportError("you need to have the svn version of reportlab installed")


_check_reportlab()


# import reportlab
# reportlab.rl_config.platypus_link_underline = 1


log = log.Log("rlwriter")





def flatten(x):
    result = []
    for el in x:
        if hasattr(el, "__iter__") and not isinstance(el, str):
            result.extend(flatten(el))
        else:
            result.append(el)
    return result


def isInline(objs):
    return all(isinstance(obj, str) for obj in flatten(objs))


def buildPara(txtList, style=text_style(), txt_style=None):
    _txt = "".join(txtList)
    _txt = _txt.strip()
    if txt_style:
        _txt = "{start}{txt}{end}".format(
            start="".join(txt_style["start"]),
            end="".join(txt_style["end"]),
            txt=_txt,
        )
    if len(_txt) > 0:
        try:
            return [Paragraph(_txt, style)]
        except:
            traceback.print_exc()
            log.warning("reportlab paragraph error:", repr(_txt))
            return []
    else:
        return []


class ReportlabError(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class RlWriter:
    def __init__(
        self, env=None, strict=False, debug=False, mathcache=None, lang=None, test_mode=False
    ):
        localedir = os.path.join(os.path.abspath(os.path.dirname(__file__)), "locale")
        translation = gettext.NullTranslations()
        if lang:
            try:
                translation = gettext.translation("mwlib.rl", localedir, [lang])
            except OSError as exc:
                log.warn(str(exc))
        translation.install()

        self.font_switcher = fontconfig.RLFontSwitcher()

        self.rtl = False
        pdfstyles.default_latin_font = pdfstyles.default_font
        self.word_wrap = None
        if lang in ["ja", "ch", "ko", "zh"]:
            self.word_wrap = "CJK"
            pdfstyles.word_wrap = self.word_wrap
        else:
            self.font_switcher.space_cjk = True
        if lang in [
            "am",
            "ar",
            "arc",
            "arz",
            "bcc",
            "bqi",
            "ckb",
            "dv",
            "dz",
            "fa",
            "glk",
            "ha",
            "he",
            "ks",
            "ku",
            "mzn",
            "pnb",
            "ps",
            "sd",
            "ug",
            "ur",
            "yi",
        ]:
            self.set_rtl(True)
            # setting Nazli as default shifts the text a little to the top
            arabic_font = self.font_switcher.getfont_for_script("arabic")
            if arabic_font:
                pdfstyles.default_font = arabic_font
                pdfstyles.serif_font = arabic_font
                pdfstyles.sans_font = arabic_font
            rl_config.rtl = True

        self.env = env
        if self.env is not None:
            self.book = self.env.metabook
            self.imgDB = env.images
        else:
            self.imgDB = None

        self.strict = strict
        self.debug = debug
        self.test_mode = test_mode

        try:
            strict_server = self.env.wiki.siteinfo["general"]["server"] in [
                "http://de.wikipedia.org"
            ]
        except:
            strict_server = False
        if strict_server:
            self.license_checker = LicenseChecker(image_db=self.imgDB, filter_type="whitelist")
        else:
            self.license_checker = LicenseChecker(image_db=self.imgDB, filter_type="blacklist")
        self.license_checker.read_licenses_csv()

        self.img_meta_info = {}
        self.img_count = 0

        self.font_switcher.font_paths = fontconfig.font_paths
        self.font_switcher.register_default_font(pdfstyles.default_font)
        self.font_switcher.registerFontDefinitionList(fontconfig.fonts)
        self.font_switcher.registerReportlabFonts(fontconfig.fonts)

        self.tc = TreeCleaner([], save_reports=self.debug, rtl=self.rtl)
        self.tc.skipMethods = pdfstyles.treecleaner_skip_methods
        self.tc.contentWithoutTextClasses.append(advtree.ReferenceList)

        self.cnt = CustomNodeTransformer()
        self.formatter = RLFormatter(font_switcher=self.font_switcher)

        self.image_utils = ImageUtils(
            pdfstyles.print_width,
            pdfstyles.print_height,
            pdfstyles.img_default_thumb_width,
            pdfstyles.img_min_res,
            pdfstyles.img_max_thumb_width,
            pdfstyles.img_max_thumb_height,
            pdfstyles.img_inline_scale_factor,
            pdfstyles.print_width_px,
        )

        self.references = []
        self.ref_name_map = {}
        self.listIndentation = 0  # nesting level of lists
        self.listCounterID = 1
        self.tmpImages = set()
        self.namedLinkCount = 1
        self.table_nesting = 0
        self.table_size_calc = 0
        self.tablecount = 0
        self.paraIndentLevel = 0

        self.gallery_mode = False
        self.ref_mode = False
        self.license_mode = False
        self.inline_mode = 0

        self.linkList = []
        self.disable_group_elements = False
        self.fail_safe_rendering = False

        self.sourceCount = 0
        self.currentColCount = 0
        self.math_cache_dir = mathcache or os.environ.get("MWLIBRL_MATHCACHE")
        self.tmpdir = tempfile.mkdtemp()
        self.bookmarks = []
        self.colwidth = 0

        self.articleids = []
        self.layout_status = None
        self.toc_entries = []
        self.toc_renderer = TocRenderer()
        self.reference_list_rendered = False
        self.article_meta_info = []
        self.url_map = {}
        self.fixed_images = {}

    def ignore(self, obj):
        return []

    def groupElements(self, elements):
        """Group reportlab flowables into KeepTogether flowables
        to achieve meaningful pagebreaks

        @type elements: [reportlab.platypus.flowable.Flowable]
        @rtype: [reportlab.platypus.flowable.Flowable]
        """
        groupedElements = []
        group = []

        def isHeading(e):
            return isinstance(e, HRFlowable) or (
                hasattr(e, "style") and e.style.name.startswith("heading_style")
            )

        groupHeight = 0
        while elements:
            if not group:
                if isHeading(elements[0]):
                    group.append(elements.pop(0))
                else:
                    groupedElements.append(elements.pop(0))
            else:
                last = group[-1]
                if not isHeading(last):
                    try:
                        w, h = last.wrap(print_width, print_height)
                    except:
                        h = 0
                    groupHeight += h
                    if groupHeight > print_height / 10 or isinstance(
                        elements[0], NotAtTopPageBreak
                    ):  # 10 % of page_height
                        groupedElements.append(SmartKeepTogether(group))
                        group = []
                        groupHeight = 0
                    else:
                        group.append(elements.pop(0))
                else:
                    group.append(elements.pop(0))
        if group:
            groupedElements.append(SmartKeepTogether(group))

        return groupedElements

    def check_direction(self, node):
        original = self.rtl
        try:
            direction = node.vlist.get("dir", "") or node.vlist.get("style", {}).get(
                "direction", ""
            )
        except AttributeError:
            pass
        else:
            direction = direction.lower().strip()
            if direction == "ltr":
                self.set_rtl(False)
            elif direction == "rtl":
                self.set_rtl(True)
        return original

    def set_rtl(self, rtl):
        self.rtl = rtl
        if rtl is True:
            pdfstyles.word_wrap = "RTL"
        else:
            pdfstyles.word_wrap = self.word_wrap

    def handle_page_break(self, node, mode="before"):
        # mode:
        # before for page-break-before
        # after for page-break-after
        css_style = None
        if node.vlist:
            css_style = node.vlist.get("style", None)
            if css_style:
                page_break = css_style.get("page-break-%s" % mode, None)
        if css_style and page_break:
            if page_break in ["always", "100%"]:
                return NotAtTopPageBreak()
            res = re.search(r"(\d{1,2})\%", page_break)
            if res:
                min_percent = int(res.groups()[0])
                return CondPageBreak(min_percent / 100.0 * pdfstyles.print_height)
        return None

    def write(self, obj):
        m = "write" + obj.__class__.__name__
        if not hasattr(self, m):
            log.error("unknown node:", repr(obj.__class__.__name__))
            if self.strict:
                raise writerbase.WriterError("Unkown Node: %s " % obj.__class__.__name__)
            return []
        m = getattr(self, m)
        styles = self.formatter.set_style(obj)
        original = self.check_direction(obj)
        res = m(obj)
        self.set_rtl(original)
        self.formatter.reset_style(styles)
        pb_before = self.handle_page_break(obj, "before")
        pb_after = self.handle_page_break(obj, "after")
        if pb_before:
            if not isinstance(res, list):
                res = [res]
            res.insert(0, pb_before)
        if pb_after:
            if not isinstance(res, list):
                res = [res]
            res.append(pb_after)
        return res

    def getVersion(self):
        try:
            extversion = _("mwlib.ext version: %(version)s") % {
                "version": str(_extversion.version),
            }
        except NameError:
            extversion = "mwlib.ext not used"

        version = _(
            "mwlib version: %(mwlibversion)s, mwlib.rl version: %(mwlibrlversion)s, %(mwlibextversion)s"
        ) % {
            "mwlibrlversion": rlwriterversion,
            "mwlibversion": mwlibversion,
            "mwlibextversion": extversion,
        }
        return version

    def buildArticle(self, item):
        mywiki = item.wiki
        art = mywiki.getParsedArticle(title=item.title, revision=item.revision)
        if not art:
            return  # FIXME
        try:
            ns = item.wiki.normalize_and_get_page(item.title, 0).ns
        except AttributeError:
            ns = 0
        art.ns = ns
        art.url = mywiki.getURL(item.title, item.revision) or None
        if item.displaytitle is not None:
            art.caption = item.displaytitle
        source = mywiki.getSource(item.title, item.revision)
        if source:
            art.wikiurl = source.url or ""
        else:
            art.wikiurl = None
        art.authors = mywiki.get_authors(item.title, revision=item.revision)
        advtree.build_advanced_tree(art)
        if self.debug:
            parser.show(sys.stdout, art)
            pass
        self.tc.tree = art
        self.tc.cleanAll()
        self.cnt.transformCSS(art)
        if self.debug:
            # parser.show(sys.stdout, art)
            print("\n".join([repr(r) for r in self.tc.getReports()]))
        return art

    def initReportlabDoc(self, output):
        version = self.getVersion()
        tocCallback = self.tocCallback if pdfstyles.render_toc else None
        self.doc = PPDocTemplate(
            output,
            topMargin=pdfstyles.page_margin_top,
            leftMargin=pdfstyles.page_margin_left,
            rightMargin=pdfstyles.page_margin_right,
            bottomMargin=pdfstyles.page_margin_bottom,
            title=self.book.title,
            keywords=version,
            status_callback=self.render_status,
            tocCallback=tocCallback,
        )

    def articleRenderingOK(self, node, output):
        testdoc = BaseDocTemplate(
            output,
            topMargin=pdfstyles.page_margin_top,
            leftMargin=pdfstyles.page_margin_left,
            rightMargin=pdfstyles.page_margin_right,
            bottomMargin=pdfstyles.page_margin_bottom,
            title="",
        )
        # PageTemplates are registered to self.doc in writeArticle
        doc_bak, self.doc = self.doc, testdoc
        elements = self.writeArticle(node)
        try:
            testdoc.build(elements)
            self.doc = doc_bak
            return True
        except:
            log.error("article failed:", repr(node.caption))
            tr = traceback.format_exc()
            log.error(tr)
            self.doc = doc_bak
            return False

    def addDummyPage(self):
        pt = WikiPage("")
        self.doc.addPageTemplates(pt)
        return Paragraph(" ", text_style())

    def writeBook(self, output, coverimage=None, status_callback=None):
        self.numarticles = len(self.env.metabook.articles())
        self.articlecount = 0
        self.getArticleIDs()

        if status_callback:
            self.layout_status = status_callback.getSubRange(1, 75)
            self.layout_status(status="laying out")
            self.render_status = status_callback.getSubRange(76, 100)
        else:
            self.layout_status = None
            self.render_status = None
        self.initReportlabDoc(output)

        elements = []
        self.toc_entries = []
        if pdfstyles.show_title_page:
            elements.extend(
                self.writeTitlePage(coverimage=coverimage or pdfstyles.title_page_image)
            )

        if self.numarticles == 0:
            elements.append(self.addDummyPage())
        got_chapter = False
        item_list = self.env.metabook.walk()
        if not self.fail_safe_rendering:
            elements.append(TocEntry(txt=_("Articles"), lvl="group"))
        for i, item in enumerate(item_list):
            if item.type == "Chapter":
                chapter = parser.Chapter(item.title.strip())
                if len(item_list) > i + 1 and item_list[i + 1].type == "article":
                    chapter.next_article_title = item_list[i + 1].title
                else:
                    chapter.next_article_title = ""
                elements.extend(self.writeChapter(chapter))
                got_chapter = True
            elif item.type == "article":
                art = self.buildArticle(item)
                self.imgDB = item.images
                self.license_checker.image_db = self.imgDB
                if not art:
                    continue
                if got_chapter:
                    art.has_preceeding_chapter = True
                    got_chapter = False
                if self.fail_safe_rendering and not self.articleRenderingOK(copy.deepcopy(art), output):
                        art.renderFailed = True
                art_elements = self.writeArticle(art)
                del art
                elements.extend(self.groupElements(art_elements))

        try:
            self.renderBook(elements, output)
            log.info("RENDERING OK")
            shutil.rmtree(self.tmpdir, ignore_errors=True)
            return
        except MemoryError:
            shutil.rmtree(self.tmpdir, ignore_errors=True)
            raise
        except Exception as err:
            traceback.print_exc()
            log.error("RENDERING FAILED: %r" % err)
            if self.fail_safe_rendering:
                log.error("GIVING UP")
                shutil.rmtree(self.tmpdir, ignore_errors=True)
                raise RuntimeError("Giving up.")
            else:
                self.fail_safe_rendering = True
                self.writeBook(output, coverimage=coverimage, status_callback=status_callback)

    def renderBook(self, elements, output):
        if pdfstyles.show_article_attribution:
            elements.append(TocEntry(txt=_("References"), lvl="group"))
            elements.append(self._getPageTemplate(_("Article Sources and Contributors")))
            elements.append(NotAtTopPageBreak())
            elements.extend(self.writeArticleMetainfo())
            elements.append(self._getPageTemplate(_("Image Sources, Licenses and Contributors")))
            if self.numarticles > 1:
                elements.append(NotAtTopPageBreak())
            elements.extend(self.writeImageMetainfo())

        if not self.debug:
            elements.extend(self.renderLicense())

        self.render_status(status="rendering", article="")

        if not self.fail_safe_rendering:
            self.doc.bookmarks = self.bookmarks

        # debughelper.dumpElements(elements)

        log.info("start rendering: %r" % output)

        try:
            gc.collect()
            if linuxmem:
                log.info("memory usage after laying out:", linuxmem.memory())
            self.doc.build(elements)
            if pdfstyles.render_toc and self.numarticles > 1:
                err = self.toc_renderer.build(
                    output, self.toc_entries, has_title_page=bool(self.book.title), rtl=self.rtl
                )
                if err:
                    log.warning(
                        "TOC not rendered. Probably pdftk is not properly installed. returncode: %r"
                        % err
                    )
            if linuxmem:
                log.info("memory usage after reportlab rendering:", linuxmem.memory())
        except:
            traceback.print_exc()
            log.info("rendering failed - trying safe rendering")
            raise

        license_stats_dir = os.environ.get("MWLIBLICENSESTATS")
        if license_stats_dir and os.path.exists(license_stats_dir):
            self.license_checker.dump_unknown_licenses(license_stats_dir)
            if self.debug:
                print(self.license_checker.dump_stats())

    def renderLicense(self):
        self.license_mode = True
        elements = []
        if not pdfstyles.show_wiki_license:
            return []
        if self.env.getLicenses():
            elements.append(TocEntry(txt=_("Article Licenses"), lvl="group"))

        for license in self.env.getLicenses():
            license_node = uparser.parse_string(
                title=_(license.title), raw=license.wikitext, wikidb=license._wiki
            )
            advtree.build_advanced_tree(license_node)
            self.tc.tree = license_node
            self.tc.cleanAll()
            elements.extend(self.writeArticle(license_node))
        self.license_mode = False
        return elements

    def getArticleIDs(self):
        self.articleids = []
        for item in self.env.metabook.walk():
            if item.type != "article":
                continue
            title = item.displaytitle or item.title

            source = item.wiki.getSource(item.title, item.revision)
            wikiurl = source.url if source else item.title
            article_id = self.buildArticleID(wikiurl, title)
            self.articleids.append(article_id)

    def tocCallback(self, info):
        self.toc_entries.append(info)

    def writeTitlePage(self, coverimage=None):
        # FIXME: clean this up. there seems to be quite a bit of deprecated here
        title = self.book.title
        subtitle = self.book.subtitle

        if not title:
            return []
        first_article_title = None
        for item in self.book.walk():
            if item.type == "Chapter":  # dont set page header if pdf starts with a chapter
                break
            if item.type == "article":
                first_article_title = self.renderArticleTitle(item.displaytitle or item.title)
                break
        self.doc.addPageTemplates(TitlePage(cover=coverimage))
        elements = []
        elements.append(Paragraph(self.formatter.clean_text(title), text_style(mode="booktitle")))
        if subtitle:
            elements.append(
                Paragraph(self.formatter.clean_text(subtitle), text_style(mode="booksubtitle"))
            )
        if not first_article_title:
            return elements
        self.doc.addPageTemplates(WikiPage(first_article_title, rtl=self.rtl))
        elements.append(NextPageTemplate(first_article_title.encode("utf-8")))
        elements.append(PageBreak())
        return elements

    def _getPageTemplate(self, title):
        template_title = self.renderArticleTitle(title)
        page_template = WikiPage(template_title, rtl=self.rtl)
        self.doc.addPageTemplates(page_template)
        return NextPageTemplate(template_title)

    def writeChapter(self, chapter):
        hr = HRFlowable(
            width="80%",
            spaceBefore=6,
            spaceAfter=0,
            color=pdfstyles.chapter_rule_color,
            thickness=0.5,
        )

        title = self.renderArticleTitle(chapter.caption)
        if self.inline_mode == 0 and self.table_nesting == 0:
            chapter_anchor = '<a name="%s" />' % len(self.bookmarks)
            self.bookmarks.append((title, "Chapter"))
        else:
            chapter_anchor = ""
        chapter_para = Paragraph(f"{title}{chapter_anchor}", heading_style("Chapter"))
        elements = []

        elements.append(self._getPageTemplate(""))
        elements.extend([NotAtTopPageBreak(), hr, chapter_para, hr])
        elements.append(TocEntry(txt=title, lvl="Chapter"))
        elements.append(self._getPageTemplate(chapter.next_article_title))
        elements.extend(self.renderChildren(chapter))

        return elements

    def writeSection(self, obj):
        lvl = getattr(obj, "level", 4)
        if self.license_mode:
            headingStyle = heading_style("License")
        else:
            headingStyle = heading_style("section", lvl=lvl + 1)
        if not obj.children:
            return ""
        self.formatter.section_title_mode = True
        try:
            heading_txt = "".join(self.renderInline(obj.children[0])).strip()
        except TypeError:
            heading_txt = ""
        self.formatter.section_title_mode = False

        if 1 <= lvl <= 4 and self.inline_mode == 0 and self.table_nesting == 0:
            anchor = '<a name="%d"/>' % len(self.bookmarks)
            bm_type = "article" if lvl == 1 else "heading%s" % lvl
            self.bookmarks.append((obj.children[0].get_all_display_text(), bm_type))
        else:
            anchor = ""
        elements = [
            Paragraph(
                f'<font name="{headingStyle.fontName}"><b>{heading_txt}</b></font>{anchor}',
                headingStyle,
            )
        ]

        if self.table_size_calc == 0:
            obj.remove_child(obj.children[0])
        elements.extend(self.renderMixed(obj))

        return elements

    def renderFailedNode(self, node, infoText):
        txt = node.get_all_display_text()
        txt = xmlescape(txt)
        elements = []
        elements.extend(
            [Spacer(0, 1 * cm), HRFlowable(width="100%", thickness=2), Spacer(0, 0.5 * cm)]
        )
        elements.append(Paragraph(infoText, text_style(in_table=False)))
        elements.append(Spacer(0, 0.5 * cm))
        elements.append(Paragraph(txt, text_style(in_table=False)))
        elements.extend(
            [Spacer(0, 0.5 * cm), HRFlowable(width="100%", thickness=2), Spacer(0, 1 * cm)]
        )
        return elements

    def buildArticleID(self, wikiurl, article_name):
        tmplink = advtree.Link()
        tmplink.target = article_name
        tmplink.capitalizeTarget = (
            True  # this is a hack, this info should pulled out of the environment if available
        )
        # tmplink._normalizeTarget() # FIXME: this is currently removed from mwlib. we need to check URL handling in mwlib
        idstr = f"{wikiurl}{tmplink.target}"
        m = md5(idstr.encode("utf-8"))
        return m.hexdigest()

    def _filterAnonIpEdits(self, authors):
        if authors:
            authors_text = ", ".join([a for a in authors if a != "ANONIPEDITS:0"])
            authors_text = re.sub(
                r"ANONIPEDITS:(?P<num>\d+)", r"\g<num> %s" % _("anonymous edits"), authors_text
            )
            authors_text = self.formatter.clean_text(authors_text)
        else:
            authors_text = "-"
        return authors_text

    def writeArticleMetainfo(self):
        elements = []
        title = self.formatter.clean_text(_("Article Sources and Contributors"))
        elements.append(Paragraph("<b>%s</b>" % title, heading_style(mode="article")))
        elements.append(TocEntry(txt=title, lvl="article"))
        for title, url, authors in self.article_meta_info:
            authors_text = self._filterAnonIpEdits(authors)
            txt = (
                "<b>{title}</b> &nbsp;<i>{source_label}</i>: {source} &nbsp;<i>{contribs_label}</i>: {contribs} ".format(
                    title=title,
                    source_label=self.formatter.clean_text(_("Source")),
                    source=self.formatter.clean_text(url),
                    contribs_label=self.formatter.clean_text(_("Contributors")),
                    contribs=authors_text,
                )
            )
            elements.append(Paragraph(txt, text_style("attribution")))
        return elements

    def writeImageMetainfo(self):
        if not self.img_meta_info:
            return []
        elements = []
        title = self.formatter.clean_text(_("Image Sources, Licenses and Contributors"))
        elements.append(Paragraph("<b>%s</b>" % title, heading_style(mode="article")))
        elements.append(TocEntry(txt=title, lvl="article"))
        for _, title, url, license, authors in sorted(self.img_meta_info.values()):
            authors_text = self._filterAnonIpEdits(authors)
            if not license:
                license = _("unknown")
            license_txt = "<i>{license_label}</i>: {license} &nbsp;".format(
                license_label=self.formatter.clean_text(_("License")),
                license=self.formatter.clean_text(license),
            )
            txt = (
                "<b>{title}</b> &nbsp;<i>{source_label}</i>: {source} &nbsp;{license_txt}<i>{contribs_label}</i>: {contribs} ".format(
                    title=self.formatter.clean_text(title),
                    source_label=self.formatter.clean_text(_("Source")),
                    source=self.formatter.clean_text(url),
                    license_txt=license_txt,
                    contribs_label=self.formatter.clean_text(_("Contributors")),
                    contribs=authors_text,
                )
            )
            elements.append(Paragraph(txt, text_style("img_attribution")))
        return elements

    def cleanTitle(self, node):
        if node.__class__ not in [
            advtree.Emphasized,
            advtree.Strong,
            advtree.Text,
            advtree.Sup,
            advtree.Sub,
            advtree.Node,
            advtree.Strike,
        ]:
            node.parent.remove_child(node)
        else:
            for c in node.children:
                self.cleanTitle(c)

    def renderArticleTitle(self, raw):
        title_node = uparser.parse_string(title="", raw=raw, expand_templates=False)
        advtree.build_advanced_tree(title_node)
        title_node.__class__ = advtree.Node
        self.cleanTitle(title_node)
        res = self.renderInline(title_node)
        return "".join(res)

    def writeArticle(self, article):
        if self.license_mode and self.debug:
            return []
        self.references = []
        title = self.renderArticleTitle(article.caption)

        log.info("rendering: %r" % (article.url or article.caption))
        if self.layout_status:
            self.layout_status(article=article.caption)
            self.articlecount += 1
        elements = []
        if hasattr(self, "doc"):  # doc is not present if tests are run
            elements.append(self._getPageTemplate(title))
            # FIXME remove the getPrevious below
            if self.license_mode:
                if self.numarticles > 1:
                    elements.append(NotAtTopPageBreak())
            elif not getattr(article, "has_preceeding_chapter", False) or isinstance(
                article.get_previous(), advtree.Article
            ):
                if pdfstyles.page_break_after_article:  # if configured and preceded by an article
                    elements.append(NotAtTopPageBreak())
                elif miscutils.article_starts_with_infobox(article, max_text_until_infobox=100):
                    elements.append(CondPageBreak(pdfstyles.article_start_min_space_infobox))
                else:
                    elements.append(CondPageBreak(pdfstyles.article_start_min_space))

        if self.inline_mode == 0 and self.table_nesting == 0:
            heading_anchor = '<a name="%d"/>' % len(self.bookmarks)
            self.bookmarks.append((article.caption, "article"))
        else:
            heading_anchor = ""

        # add anchor for internal links
        url = getattr(article, "url", None)
        if url:
            article_id = self.buildArticleID(article.wikiurl, article.caption)
            heading_anchor = "{}{}".format(heading_anchor, '<a name="%s" />' % article_id)
        else:
            article_id = None

        heading_para = Paragraph(f"<b>{title}</b>{heading_anchor}", heading_style("article"))
        elements.append(heading_para)
        elements.append(TocEntry(txt=title, lvl="article"))

        if pdfstyles.show_article_hr:
            elements.append(
                HRFlowable(
                    width="100%",
                    hAlign="LEFT",
                    thickness=1,
                    spaceBefore=0,
                    spaceAfter=10,
                    color=colors.black,
                )
            )
        else:
            elements.append(Spacer(0, 10))

        if not hasattr(
            article, "renderFailed"
        ):  # if rendering of the whole book failed, failed articles are flagged
            elements.extend(self.renderMixed(article))
        else:
            articleFailText = _(
                "<strong>WARNING: Article could not be rendered - outputting plain text.</strong><br/>Potential causes of the problem are: (a) a bug in the pdf-writer software (b) problematic Mediawiki markup (c) table is too wide"
            )
            elements.extend(self.renderFailedNode(article, articleFailText))

        # check for non-flowables
        elements = [e for e in elements if not isinstance(e, str)]
        elements = self.floatImages(elements)
        elements = self.tabularizeImages(elements)

        if self.references:
            ref_elements = [
                Paragraph("<b>" + _("References") + "</b>", heading_style("section", lvl=3))
            ]
            ref_elements.extend(self.writeReferenceList())
            if isinstance(elements[-1], CondPageBreak):
                elements[-1:-1] = ref_elements
            else:
                elements.extend(ref_elements)

        if not self.license_mode and not self.fail_safe_rendering:
            self.article_meta_info.append((title, url, getattr(article, "authors", "")))

        if self.layout_status:
            if not self.numarticles:
                self.layout_status(progress=100)
            else:
                self.layout_status(progress=100 * self.articlecount / self.numarticles)

        self.reference_list_rendered = False
        return elements

    def writeParagraph(self, obj):
        first_leaf = obj.get_first_leaf()
        if hasattr(first_leaf, "caption"):
            first_leaf.caption = first_leaf.caption.lstrip()
        if getattr(obj, "is_header", False):
            style = text_style(mode="center", in_table=self.table_nesting)
        else:
            style = None
        return self.renderMixed(obj, style)

    def floatImages(self, nodes):
        """Floating images are combined with paragraphs.
        This is achieved by sticking images and paragraphs
        into a FiguresAndParagraphs flowable

        @type nodes: [reportlab.platypus.flowable.Flowable]
        @rtype: [reportlab.platypus.flowable.Flowable]
        """

        def getMargins(align):
            if align == "right":
                return pdfstyles.img_margins_float_right
            elif align == "left":
                return pdfstyles.img_margins_float_left
            return pdfstyles.img_margins_float

        combinedNodes = []
        floatingNodes = []
        figures = []
        lastNode = None

        def gotSufficientFloats(figures, paras):
            hf = 0
            hp = 0
            maxImgWidth = 0
            for f in figures:
                # assume 40 chars per line for caption text
                hf += (
                    f.imgHeight
                    + f.margin[0]
                    + f.margin[2]
                    + f.padding[0]
                    + f.padding[2]
                    + f.cs.leading * max(int(len(f.captionTxt) / 40), 1)
                )
                maxImgWidth = max(maxImgWidth, f.imgWidth)
            for p in paras:
                if isinstance(p, Paragraph):
                    w, h = p.wrap(print_width - maxImgWidth, print_height)
                    h += p.style.spaceBefore + p.style.spaceAfter
                    hp += h
            return hp > hf - 10

        for n in nodes:  # FIXME: somebody should clean up this mess
            if isinstance(lastNode, Figure) and isinstance(n, Figure):
                if getattr(n, "float_figure", False):
                    figures.append(n)
                else:
                    combinedNodes.extend(figures)
                    combinedNodes.extend([Spacer(0, 0.5 * cm), n])
                    figures = []
            else:
                if not figures:
                    if getattr(n, "float_figure", False):
                        figures.append(n)
                    else:
                        combinedNodes.append(n)
                else:
                    if (
                        hasattr(n, "style")
                        and n.style.flowable is True
                        and not gotSufficientFloats(figures, floatingNodes)
                    ):  # newpara
                        floatingNodes.append(n)
                    else:
                        if len(floatingNodes) > 0:
                            if (
                                hasattr(floatingNodes[-1], "style")
                                and floatingNodes[-1].style.name.startswith("heading_style")
                                and floatingNodes[-1].style.flowable is True
                            ):  # prevent floating headings before nonFloatables
                                noFloatNode = floatingNodes[-1]
                                floatingNodes = floatingNodes[:-1]
                            else:
                                noFloatNode = None
                            if len(floatingNodes) == 0:
                                combinedNodes.extend(figures)
                                figures = []
                                combinedNodes.append(noFloatNode)
                                if getattr(n, "float_figure", False):
                                    figures.append(n)
                                else:
                                    combinedNodes.append(n)
                                lastNode = n
                                continue
                            fm = getMargins(figures[0].align or "right")
                            combinedNodes.append(
                                FiguresAndParagraphs(
                                    figures, floatingNodes, figure_margin=fm, rtl=self.rtl
                                )
                            )
                            if noFloatNode:
                                combinedNodes.append(noFloatNode)
                            figures = []
                            floatingNodes = []
                            if getattr(n, "float_figure", False):
                                figures.append(n)
                            else:
                                combinedNodes.append(n)
                        else:
                            combinedNodes.extend(figures)
                            combinedNodes.append(n)
                            figures = []
            lastNode = n

        if figures and floatingNodes:
            fm = getMargins(figures[0].align or "right")
            combinedNodes.append(
                FiguresAndParagraphs(figures, floatingNodes, figure_margin=fm, rtl=self.rtl)
            )
        else:
            combinedNodes.extend(figures + floatingNodes)

        return combinedNodes

    def tabularizeImages(self, nodes):
        """consecutive images that couldn't be combined with paragraphs
        are put into a 2 column table
        """
        finalNodes = []
        figures = []

        def scaleImages(images):
            scaled_images = []
            for img in images:
                ar = img.imgWidth / img.imgHeight
                w = print_width / 2 - (
                    img.margin[1] + img.margin[3] + img.padding[1] + img.padding[3]
                )
                h = w / ar
                if w > img.imgWidth:
                    scaled = img
                else:
                    scaled = Figure(
                        img.imgPath,
                        img.captionTxt,
                        img.cs,
                        imgWidth=w,
                        imgHeight=h,
                        margin=img.margin,
                        padding=img.padding,
                        borderColor=img.borderColor,
                        url=img.url,
                    )
                scaled_images.append(scaled)
            return scaled_images

        for n in nodes:
            if isinstance(n, Figure):
                figures.append(n)
            else:
                if len(figures) > 1:
                    figures = scaleImages(figures)
                    data = [
                        [figures[2 * i], figures[2 * i + 1]] for i in range(int(len(figures) / 2))
                    ]
                    if len(figures) % 2 != 0:
                        data.append([figures[-1], ""])
                    table = Table(data)
                    finalNodes.append(table)
                    figures = []
                else:
                    if figures:
                        finalNodes.append(figures[0])
                        figures = []
                    finalNodes.append(n)
        if len(figures) > 1:
            figures = scaleImages(figures)
            data = [[figures[2 * i], figures[2 * i + 1]] for i in range(int(len(figures) / 2))]
            if len(figures) % 2 != 0:
                data.append([figures[-1], ""])
            table = Table(data)
            finalNodes.append(table)
        else:
            finalNodes.extend(figures)
        return finalNodes

    def writePreFormatted(self, obj):
        self.formatter.pre_mode = True
        rtl, self.rtl = self.rtl, False
        txt = self.renderInline(obj)
        self.rtl = rtl
        t = "".join(txt)
        t = re.sub("<br */>", "\n", t)
        t = t.replace("\t", " " * pdfstyles.tabsize)
        self.formatter.pre_mode = False
        if not len(t):
            return []

        avail_width = self.getAvailWidth()
        width = None
        style = text_style(mode="preformatted", in_table=self.table_nesting)
        while not width or width > avail_width:
            pre = XPreformatted(t, style)
            width, _ = pre.wrap(avail_width, pdfstyles.page_height)
            style.fontSize -= 0.5
            if style.fontSize < pdfstyles.min_preformatted_size:
                style = text_style(mode="preformatted", in_table=self.table_nesting)
                char_limit = max(
                    1, int(pdfstyles.source_max_line_len / (max(1, 0.75 * self.currentColCount)))
                )
                t = self.breakLongLines(t, char_limit)
                pre = XPreformatted(t, style)
                break
        return [pre]

    def writeNode(self, obj):
        return self.renderMixed(obj)

    def renderText(self, txt, **kwargs):
        return self.formatter.style_text(txt, kwargs)

    def writeText(self, obj):
        return [self.renderText(obj.caption)]

    def renderInline(self, node):
        txt = []
        self.inline_mode += 1
        for child in node.children:
            res = self.write(child)
            if isInline(res):
                txt.extend(res)
            else:
                log.warning(
                    node.__class__.__name__, " contained block element: ", child.__class__.__name__
                )
                txt.append(self.renderText(child.get_all_display_text()))
        self.inline_mode -= 1

        text_color = styleutils.rgb_color_from_node(node)
        if text_color:
            hex_col = "".join("%02x" % int(c * 255) for c in text_color)
            txt.insert(0, '<font color="#%s">' % hex_col)
            txt.append("</font>")
        return txt

    def renderMixed(self, node, para_style=None, textPrefix=None):
        if not para_style:
            if self.license_mode:
                para_style = text_style("License")
            else:
                para_style = text_style(
                    indent_lvl=self.paraIndentLevel, in_table=self.table_nesting
                )
        elif self.license_mode:
            para_style.fontSize = max(text_style("License").fontSize, para_style.fontSize - 4)
            para_style.leading = 1

        math_nodes = node.get_child_nodes_by_class(advtree.Math)
        if math_nodes:
            max_source_len = max([len(math.caption) for math in math_nodes])
            if max_source_len > pdfstyles.no_float_math_len:
                para_style.flowable = False

        txt = []
        if textPrefix:
            txt.append(textPrefix)
        items = []

        if isinstance(node, advtree.Node):  # set node styles like text/bg colors, alignment
            text_color = styleutils.rgb_color_from_node(node)
            background_color = styleutils.rgb_bg_color_from_node(node)
            if text_color:
                para_style.textColor = text_color
            if background_color:
                para_style.backColor = background_color
            align = styleutils.get_text_alignment(node)
            if align in ["right", "center", "justify"]:
                align_map = {
                    "right": TA_RIGHT,
                    "center": TA_CENTER,
                    "justify": TA_JUSTIFY,
                }
                para_style.alignment = align_map[align]

        txt_style = None
        if node.__class__ == advtree.Cell and getattr(node, "is_header", False):
            txt_style = {  # check nesting: start: <a>,<b> --> end: </b></a>
                "start": ["<b>"],
                "end": ["</b>"],
            }
        for c in node:
            res = self.write(c)
            if isInline(res):
                txt.extend(res)
            else:
                items.extend(buildPara(txt, para_style, txt_style=txt_style))
                items.extend(res)
                txt = []
        if not len(items):
            return buildPara(txt, para_style, txt_style=txt_style)
        else:
            items.extend(buildPara(txt, para_style, txt_style=txt_style))
            return items

    def renderChildren(self, n):
        items = []
        for c in n:
            items.extend(self.write(c))
        return items

    def writeEmphasized(self, n):
        return self.renderInline(n)

    def writeStrong(self, n):
        return self.renderInline(n)

    def writeDefinitionList(self, n):
        return self.renderChildren(n)

    def writeDefinitionTerm(self, n):
        txt = self.writeStrong(n)
        return [Paragraph("".join(txt), text_style(in_table=self.table_nesting))]

    def writeDefinitionDescription(self, n):
        return self.writeIndented(n)

    def writeIndented(self, n):
        self.paraIndentLevel += getattr(n, "indentlevel", 1)
        items = self.renderMixed(
            n, para_style=text_style(indent_lvl=self.paraIndentLevel, in_table=self.table_nesting)
        )
        self.paraIndentLevel -= getattr(n, "indentlevel", 1)
        return items

    def writeBlockquote(self, n):
        self.paraIndentLevel += 1
        items = self.renderMixed(n, text_style(mode="blockquote", in_table=self.table_nesting))
        self.paraIndentLevel -= 1
        return items

    def writeOverline(self, n):
        # FIXME: there is no way to do overline in reportlab paragraphs.
        return self.renderInline(n)

    def writeUnderline(self, n):
        return self.renderInline(n)

    writeInserted = writeUnderline

    def writeAbbreviation(self, n):
        self.formatter.underline_style += 1
        res = self.renderInline(n)
        self.formatter.underline_style -= 1
        return res

    def writeSub(self, n):
        return self.renderInline(n)

    def writeSup(self, n):
        return self.renderInline(n)

    def writeSmall(self, n):
        return self.renderInline(n)

    def writeBig(self, n):
        return self.renderInline(n)

    def writeCite(self, n):
        return self.writeEmphasized(n)

    def writeStyle(self, s):
        txt = []
        txt.extend(self.renderInline(s))
        log.warning("unknown tag node", repr(s))
        return txt

    def writeLink(self, obj):
        """Link nodes are intra wiki links"""
        href = obj.url

        # looking for internal links
        internallink = False
        if isinstance(obj, advtree.ArticleLink) and obj.url:
            a = obj.get_parent_nodes_by_class(advtree.Article)
            wikiurl = ""
            if a:
                wikiurl = getattr(a[0], "wikiurl", "")
            article_id = self.buildArticleID(wikiurl, obj.full_target)
            if article_id in self.articleids:
                internallink = True

        if not href:
            log.warning("no link target specified")
            if not obj.children:
                return []
        else:
            quote_idx = href.find('"')
            if quote_idx > -1:
                href = href[:quote_idx]
        if obj.children:
            txt = self.renderInline(obj)
            t = "".join(txt)
            if not href:
                return [t]
        else:
            txt = urllib.parse.unquote(obj.target.encode("utf-8"))
            t = self.formatter.style_text(txt)

        if not internallink:
            if not obj.target.startswith("#"):  # intrapage links are filtered
                t = f'<link href="{xmlescape(href)}">{t}</link>'
        else:
            t = f'<link href="#{article_id}">{t}</link>'

        return [t]

    def writeLangLink(self, obj):
        if obj.colon:
            return self.writeLink(obj)
        return []

    writeArticleLink = writeLink
    writeNamespaceLink = writeLink
    writeInterwikiLink = writeLink
    writeSpecialLink = writeLink

    def renderURL(self, url):
        url = xmlescape(url)
        if self.rtl:
            return url
        zws = '<font fontSize="1"> </font>'
        url = (
            url.replace("/", "/%s" % zws)
            .replace("&amp;", "&amp;%s" % zws)
            .replace(".", ".%s" % zws)
            .replace("+", "+%s" % zws)
        )
        return url

    def writeURL(self, obj):
        href = obj.caption
        if href is not None:
            quote_idx = href.find('"')
            if quote_idx > -1:
                href = href[:quote_idx]
        display_text = self.renderURL(href)
        href = xmlescape(href)
        if (
            self.table_nesting and len(href) > pdfstyles.url_ref_len and pdfstyles.url_ref_in_table
        ) and not self.ref_mode:
            return self.writeNamedURL(obj)
        if self.rtl:
            txt = f'<link href="{href}">\u202a{display_text}\u202c</link>'
        else:
            txt = f'<link href="{href}">{display_text}</link>'
        return [txt]

    def writeNamedURL(self, obj):
        href = obj.caption.strip()
        if href.startswith("//"):
            href = "http:" + href
        if not self.ref_mode and not self.reference_list_rendered:
            if not self.url_map.get(href):
                i = parser.Item()
                i.children = [advtree.URL(href)]
                self.references.append(i)
                self.url_map[href] = len(self.references)
        else:  # we are writing a reference section. we therefore directly print URLs
            txt = self.renderInline(obj)
            if any(href.startswith(url) for url in pdfstyles.url_blacklist):
                return ["".join(txt)]
            txt.append(
                ' <link href="{}">({})</link>'.format(xmlescape(href), self.renderURL(urllib.parse.unquote(href)))
            )
            return ["".join(txt)]

        if not obj.children:
            linktext = f'<link href="{xmlescape(href)}">[{self.url_map[href]}]</link>'
        else:
            linktext = self.renderInline(obj)
            linktext.append(
                ' <super><link href="{}"><font size="10">[{}]</font></link></super> '.format(xmlescape(href), self.url_map[href])
            )
            linktext = "".join(linktext).strip()
        return linktext

    def writeCategoryLink(self, obj):
        txt = []
        if obj.colon:  # CategoryLink inside the article
            if obj.children:
                txt.extend(self.renderInline(obj))
            else:
                txt.append(obj.target)
        else:  # category of the article which is suppressed
            return []
        txt = "".join(txt)
        if txt.find("|") > -1:
            txt = txt[
                : txt.find("|")
            ]  # category links sometimes seem to have more than one element. throw them away except the first one
        return ["".join(txt)]  # FIXME use writelink to generate clickable-link

    def svg2png(self, img_path):
        cmd = ["convert", img_path, "-flatten", "-coalesce", "-strip", img_path + ".png"]
        try:
            p = subprocess.Popen(cmd, shell=False)
            pid, status = os.waitpid(p.pid, 0)
            if status != 0:
                log.warning(
                    "img could not be converted. convert exited with non-zero return code:",
                    repr(cmd),
                )
                return ""
            else:
                return "%s.png" % img_path
        except OSError:
            log.warning("img could not be converted. cmd failed:", repr(cmd))
            return ""

    def getImgPath(self, target):
        if self.imgDB:
            imgPath = self.imgDB.getDiskPath(
                target, size=800
            )  # FIXME: width should be obsolete now
            if imgPath and imgPath.lower().endswith("svg"):
                imgPath = self.svg2png(imgPath)
            if imgPath:
                imgPath = imgPath.encode("utf-8")
                self.tmpImages.add(imgPath)
            if not self.license_checker.display_image(target):
                if self.debug:
                    print(
                        "filtering image",
                        target,
                        self.license_checker.get_license_display_name(target),
                    )
                return None
        else:
            imgPath = ""
        return imgPath

    def _fixBrokenImages(self, img_node, img_path):
        if img_path in self.fixed_images:
            return self.fixed_images[img_path]
        self.fixed_images[img_path] = -1

        try:
            img = PilImage.open(img_path)
        except OSError:
            log.warning("image can not be opened by PIL: %r" % img_path)
            return -1
        if not isinstance(img.info.get("transparency", 0), int):
            log.warning("image contains invalid transparency info - skipping")
            return -1
        cmds = []
        base_cmd = [
            "convert",
            "-limit",
            "memory",
            "32000000",
            "-limit",
            "map",
            "64000000",
            "-limit",
            "disk",
            "64000000",
            "-limit",
            "area",
            "64000000",
        ]
        if img.info.get("interlace", 0) == 1:
            cmds.append(base_cmd + [img_path, "-interlace", "none", img_path])
        if img.mode == "P":  # ticket 324
            cmds.append(
                base_cmd + [img_path, img_path]
            )  # we esentially do nothing...but this seems to fix the problems
        if img.mode == "LA":  # ticket 429
            cleaned = PilImage.new("LA", img.size)
            new_data = []
            for pixel in img.getdata():
                if pixel[1] == 0:
                    new_data.append((255, 0))
                else:
                    new_data.append(pixel)
            cleaned.putdata(new_data)
            cleaned.save(img_path)
            img = PilImage.open(img_path)
        if img.mode == "RGBA":
            # ticket 901, image: http://en.wikipedia.org/wiki/File:WiMAXArchitecture.svg
            # correct preserving alpha:
            # convert broken.png white1000.png -compose Multiply -composite +matte final.png
            cmds.append(
                base_cmd
                + [
                    "-background",
                    "white",
                    "-alpha",
                    "Background",
                    "-alpha",
                    "off",
                    img_path,
                    img_path,
                ]
            )

        for cmd in cmds:
            try:
                ret = subprocess.call(cmd)
                if ret != 0:
                    log.warning(
                        "converting broken image failed (return code: %d): %r" % (ret, img_path)
                    )
                    return ret
            except OSError:
                log.warning("converting broken image failed (OSError): %r" % img_path)
                raise
        try:
            del img
        except:
            log.warning("image can not be opened by PIL: %r" % img_path)
            raise
        self.fixed_images[img_path] = 0
        return 0

    def set_svg_default_size(self, img_node):
        image_info = self.imgDB.imageinfo.get(img_node.full_target, {})
        if image_info.get("url", "").endswith(".svg"):
            w = image_info.get("width")
            h = image_info.get("height")
            if (
                w
                and h
                and img_node.width is None
                and img_node.height is None
                and img_node.isInline()
            ):
                img_node.width = w
                img_node.height = h

    def writeImageLink(self, img_node):
        if img_node.colon is True:
            items = []
            for node in img_node.children:
                items.extend(self.write(node))
            return items

        img_path = self.getImgPath(img_node.target)

        if not img_path:
            if img_node.target is None:
                img_node.target = ""
            log.warning("invalid image url (obj.target: %r)" % img_node.target)
            return []

        try:
            ret = self._fixBrokenImages(img_node, img_path)
            if ret != 0:
                return []
        except:
            import traceback

            traceback.print_exc()
            log.warning("image skipped")
            return []

        max_width = self.colwidth
        if self.table_nesting > 0 and not max_width:
            cell = img_node.get_parent_nodes_by_class(advtree.Cell)
            if cell:
                max_width = print_width / len(cell[0].get_all_siblings()) - 10
        max_height = pdfstyles.img_max_thumb_height * pdfstyles.print_height
        if self.table_nesting > 0:
            max_height = print_height / 4  # fixme this needs to be read from config
        if self.gallery_mode:
            max_height = print_height / 3  # same as above

        self.set_svg_default_size(img_node)

        w, h = self.image_utils.get_image_size(
            img_node, img_path, max_print_width=max_width, max_print_height=max_height
        )

        align = img_node.align
        if align in [None, "none"]:
            align = styleutils.get_text_alignment(img_node)
        if advtree.Center in [p.__class__ for p in img_node.get_parents()]:
            align = "center"
        txt = []
        if img_node.render_caption:
            txt = self.renderInline(img_node)

        is_inline = img_node.isInline()

        if pdfstyles.link_images:
            url = self.imgDB.getDescriptionURL(img_node.target) or self.imgDB.getURL(
                img_node.target
            )
        else:
            url = None

        if url:
            linkstart = '<link href="%s"> ' % (
                xmlescape(url)
            )  # spaces are needed, otherwise link is not present. probably b/c of a inline image bug of reportlab
            linkend = " </link>"
        else:
            linkstart = ""
            linkend = ""

        img_name = img_node.target
        if not self.img_meta_info.get(img_name):
            self.img_count += 1
            url = self.imgDB.getDescriptionURL(img_name) or self.imgDB.getURL(img_name)
            if url and pdfstyles.link_images:
                url = urllib.parse.unquote(url.encode("utf-8"))
            else:
                url = ""
            if not self.test_mode:
                license_name = self.license_checker.get_license_display_name(img_name)
                contributors = self.imgDB.getContributors(img_node.target)
            else:
                license_name = ""
                contributors = ""
            self.img_meta_info[img_name] = (
                self.img_count,
                img_name,
                url,
                license_name,
                contributors,
            )

        if is_inline:
            txt = (
                '{linkstart}<img src="{src}" width="{width:f}pt" height="{height:f}pt" valign="{align}"/>{linkend}'.format(
                    src=str(img_path, "utf-8"),
                    width=w,
                    height=h,
                    align="bottom",
                    linkstart=linkstart,
                    linkend=linkend,
                )
            )
            return [txt]
        captionTxt = "".join(txt)
        figure = Figure(
            img_path,
            captionTxt=captionTxt,
            captionStyle=text_style("figure", in_table=self.table_nesting),
            imgWidth=w,
            imgHeight=h,
            margin=(0.2 * cm, 0.2 * cm, 0.2 * cm, 0.2 * cm),
            padding=(0.2 * cm, 0.2 * cm, 0.2 * cm, 0.2 * cm),
            borderColor=pdfstyles.img_border_color,
            align=align,
            url=url,
        )
        figure.float_figure = img_node.align not in ["center", "none"]
        return [figure]

    def writeGallery(self, obj):
        self.gallery_mode = True
        try:
            perrow = int(obj.attributes.get("perrow", ""))
        except ValueError:
            perrow = None
        num_images = len(obj.get_child_nodes_by_class(advtree.ImageLink))
        if num_images == 0:
            return []
        perrow = min(6, perrow, num_images) if perrow else min(4, num_images)
        perrow = max(1, perrow)
        data = []
        row = []
        if obj.children:
            self.colwidth = print_width / perrow - 12
        colwidths = [self.colwidth + 12] * perrow

        for node in obj.children:
            if isinstance(node, advtree.ImageLink):
                node.align = (
                    "center"  # this is a hack. otherwise writeImage thinks this is an inline image
                )
                res = self.write(node)
            else:
                res = self.write(node)
                try:
                    res = buildPara(res)
                except:
                    res = Paragraph("", text_style(in_table=self.table_nesting))
            if len(row) < perrow:
                row.append(res)
            else:
                data.append(row)
                row = []
                row.append(res)
        if len(row):
            while len(row) < perrow:
                row.append("")
            data.append(row)

        row_heights = []
        aspect_ratios = []
        for row in data:
            min_height = 999999
            for cell in row:
                if cell:
                    figure = cell[0]
                    min_height = min(min_height, figure.imgHeight)
                    aspect_ratios.append(figure.imgHeight / figure.imgWidth)
            row_heights.append(min_height)

        for row_idx, row in enumerate(data):
            for cell in row:
                if cell:
                    figure = cell[0]
                    figure.i.drawWidth = row_heights[row_idx] / aspect_ratios.pop(0)
                    figure.i.drawHeight = row_heights[row_idx]

        table = Table(data, colWidths=colwidths)
        table.setStyle([("VALIGN", (0, 0), (-1, -1), "TOP")])
        self.gallery_mode = False
        caption = obj.attributes.get("caption", None)
        self.colwidth = None
        if caption:
            txt = self.formatter.style_text(caption)
            elements = buildPara(txt, heading_style(mode="tablecaption"))
            elements.append(table)
            return elements
        else:
            return [table]

    def _len(self, txt):
        in_tag = False
        length = 0
        for c in txt:
            if c == "<":
                in_tag = True
            elif c == ">":
                in_tag = False
            elif not in_tag:
                length += 1
        return length

    def _getFrags(self, txt):
        # Words = re.findall('([ \t]+|[^ \t]+)', txt)
        words = []
        word = []
        in_tag = False
        in_space = False
        for c in txt:
            if c == "<":
                in_tag = True
            if c in [" ", "\t"]:
                if not in_tag and not in_space:
                    words.append("".join(word))
                    word = []
                word.append(c)
                in_space = True
            else:
                if in_space and not in_tag:
                    words.append("".join(word))
                    word = []
                word.append(c)
                in_space = False
            if c == ">":
                in_tag = False
        if word:
            words.append("".join(word))
        return words

    def breakLongLines(self, txt, char_limit):
        broken_source = []
        for line in txt.split("\n"):
            if len(line) < char_limit:
                broken_source.append(line)
            else:
                words = self._getFrags(line)
                while words:
                    new_line = [words.pop(0)]
                    while (
                        words and (self._len("".join(new_line)) + self._len(words[0])) < char_limit
                    ):
                        new_line.append(words.pop(0))
                    broken_source.append("".join(new_line))
        return "\n".join(broken_source)

    def _writeSourceInSourceMode(self, n, src_lang, lexer, font_size):
        sourceFormatter = ReportlabFormatter(
            font_size=font_size,
            font_name="FreeMono",
            background_color="#eeeeee",
            line_numbers=False,
        )
        sourceFormatter.encoding = "utf-8"
        self.formatter.source_mode += 1

        source = "".join(self.renderInline(n))
        self.formatter.source_mode -= 1
        source = source.replace("\t", " " * pdfstyles.tabsize)
        maxCharOnLine = max([len(line) for line in source.split("\n")])
        char_limit = max(1, int(pdfstyles.source_max_line_len / (max(1, self.currentColCount))))

        if maxCharOnLine > char_limit:
            source = self.breakLongLines(source, char_limit)
        txt = ""
        try:
            txt = str(highlight(source, lexer, sourceFormatter), "utf-8")
            self.font_switcher.register_default_font(pdfstyles.default_latin_font)
            txt = self.font_switcher.fontifyText(txt)
            self.font_switcher.register_default_font(pdfstyles.default_font)
            if n.vlist.get("enclose", False) == "none":
                txt = re.sub("<para.*?>", "", txt).replace("</para>", "")
                return txt
            return XPreformatted(txt, text_style(mode="source", in_table=self.table_nesting))
        except:
            traceback.print_exc()
            log.error(
                "unsuitable lexer for source code language: {} - Lexer: {}".format(repr(src_lang), lexer.__class__.__name__)
            )
            return None

    def writeSource(self, n):
        langMap = {
            "lisp": lexers.CommonLispLexer()
        }  # custom Mapping between mw-markup source attrs to pygement lexers if get_lexer_by_name fails

        def getLexer(name):
            try:
                return lexers.get_lexer_by_name(name)
            except lexers.ClassNotFound:
                lexer = langMap.get(name)
                if lexer:
                    return lexer
                else:
                    traceback.print_exc()
                    log.error("unknown source code language: %s" % repr(name))
                    return None

        src_lang = n.vlist.get("lang", "").lower()
        lexer = getLexer(src_lang)
        if lexer:
            rtl, self.rtl = self.rtl, False
            width = None
            avail_width = self.getAvailWidth()
            font_size = pdfstyles.font_size
            while not width or width > avail_width:
                res = self._writeSourceInSourceMode(n, src_lang, lexer, font_size)
                if res.__class__ != XPreformatted:
                    break
                width, height = res.wrap(avail_width, pdfstyles.page_height)
                font_size -= 0.5
            self.rtl = rtl
            if res:
                return [res]
        return self.writePreFormatted(n)

    def writeTeletyped(self, n):
        return self.renderInline(n)

    writeCode = writeTeletyped
    writeVar = writeTeletyped

    def writeBreakingReturn(self, n):
        return ["<br />"]

    def writeHorizontalRule(self, n):
        return [
            HRFlowable(
                width="100%", spaceBefore=3, spaceAfter=6, color=colors.black, thickness=0.25
            )
        ]

    def writeIndex(self, n):
        log.warning("unhandled Index Node - rendering child nodes")
        return self.renderChildren(n)  # fixme: handle index nodes properly

    def writeReference(self, n, isLink=False):
        ref_name = n.attributes.get("name")
        if not getattr(n, "ref_num", None):
            if ref_name and not n.children:
                ref_num = self.ref_name_map.get(ref_name, "")
            else:
                i = parser.Item()
                for c in n.children:
                    i.append_child(c)
                self.references.append(i)
                ref_num = len(self.references)
                self.ref_name_map[ref_name] = ref_num
            n.ref_num = ref_num
        if getattr(n, "no_display", False):
            return []
        if isLink:
            return ["[%s]" % len(self.references)]
        else:
            return ['<super><font size="10">[%s]</font></super>' % n.ref_num]

    def writeReferenceList(self, n=None):
        if self.references:
            self.ref_mode = True
            refList = self.writeItemList(self.references, style="referencelist")
            self.references = []
            self.ref_mode = False
            self.reference_list_rendered = True
            return refList
        else:
            self.reference_list_rendered = True
            return []

    def writeCenter(self, n):
        return self.renderMixed(n, text_style(mode="center", in_table=self.table_nesting))

    def writeDiv(self, n):
        if not n.children:
            div_height = n.style.get("height")
            if div_height:
                height = min(styleutils.scale_length(div_height), pdfstyles.print_height - 20)
                if height:
                    return [Spacer(0, height)]
            return []
        if (
            getattr(n, "border", False)
            and not n.get_parent_nodes_by_class(Table)
            and not n.get_child_nodes_by_class(advtree.PreFormatted)
        ):
            return self.renderMixed(
                n,
                text_style(
                    mode="box", indent_lvl=self.paraIndentLevel, in_table=self.table_nesting
                ),
            )
        else:
            return self.renderMixed(
                n, text_style(indent_lvl=self.paraIndentLevel, in_table=self.table_nesting)
            )

    def writeSpan(self, n):
        return self.renderInline(n)

    def writeFont(self, n):  # FIXME we should evaluate the info in the fonttag
        return self.renderInline(n)

    def writeStrike(self, n):
        return self.renderInline(n)

    writeS = writeStrike
    writeDeleted = writeStrike

    def writeImageMap(self, n):
        if n.imagemap.imagelink:
            return self.write(n.imagemap.imagelink)
        else:
            return []

    def writeTagNode(self, t):
        if getattr(t, "caption", None) in ["hiero"]:
            return []
        return self.renderChildren(t)  # FIXME

    def writeItem(self, item, style="itemize", counterID=None, resetCounter=False):
        items = []
        seqReset = '<seqreset id="liCounter%d" base="0" />' % counterID if resetCounter else ""

        if style == "itemize":
            itemPrefix = "<bullet>%s</bullet>" % pdfstyles.list_item_style
        elif style == "referencelist":
            itemPrefix = '<bullet>%s[<seq id="liCounter%d" />]</bullet>' % (seqReset, counterID)
        elif style == "enumerate":
            itemPrefix = '<bullet>%s<seq id="liCounter%d" />.</bullet>' % (seqReset, counterID)
        elif style.startswith("enumerateLetter"):
            itemPrefix = (
                '<bullet>%s<seqformat id="liCounter%d" value="%s"/><seq id="liCounter%d" />.</bullet>'
                % (seqReset, counterID, style[-1], counterID)
            )
        else:
            log.warn("invalid list style:", repr(style))
            itemPrefix = ""

        listIndent = max(0, (self.listIndentation + self.paraIndentLevel))
        if self.license_mode:
            para_style = text_style(mode="licenselist", indent_lvl=listIndent)
        elif self.ref_mode:
            para_style = text_style(mode="references", indent_lvl=listIndent)
        else:
            para_style = text_style(
                mode="list", indent_lvl=listIndent, in_table=self.table_nesting
            )
        if resetCounter:  # first list item gets extra spaceBefore
            para_style.spaceBefore = text_style().spaceBefore

        leaf = item.get_first_leaf()  # strip leading spaces from list items
        if leaf and hasattr(leaf, "caption"):
            leaf.caption = leaf.caption.lstrip()
        items = self.renderMixed(item, para_style=para_style, textPrefix=itemPrefix)

        return items

    def writeItemList(self, lst, numbered=False, style="itemize"):
        self.listIndentation += 1
        items = []
        if style != "referencelist":
            if numbered or lst.numbered:
                list_style = lst.style.get("list-style-type")
                list_type = lst.vlist.get("type")
                if list_style == "lower-alpha" or list_type == "a":
                    style = "enumerateLettera"
                elif list_style == "upper-alpha" or list_type == "A":
                    style = "enumerateLetterA"
                elif list_style == "lower-roman" or list_type == "i":
                    style = "enumerateLetteri"
                elif list_style == "upper-roman" or list_type == "I":
                    style = "enumerateLetterI"
                else:
                    style = "enumerate"
            else:
                style = "itemize"
        self.listCounterID += 1
        counterID = self.listCounterID
        for i, node in enumerate(lst):
            if isinstance(node, parser.Item):
                resetCounter = (
                    i == 0
                )  # we have to manually reset sequence counters. due to w/h calcs with wrap reportlab gets confused
                item = self.writeItem(
                    node, style=style, counterID=counterID, resetCounter=resetCounter
                )
                items.extend(item)
            else:
                log.warning("got %s node in itemlist - skipped" % node.__class__.__name__)
        self.listIndentation -= 1
        return items

    def getAvailWidth(self):
        if self.table_nesting > 1 and self.colwidth:
            availwidth = self.colwidth - 2 * pdfstyles.cell_padding
        else:
            availwidth = pdfstyles.print_width - self.paraIndentLevel * pdfstyles.para_left_indent
        return availwidth

    def writeCaption(self, node):
        txt = []
        for x in node.children:
            res = self.write(x)
            if isInline(res):
                txt.extend(res)
        txt.insert(0, "<b>")
        txt.append("</b>")
        return buildPara(txt, heading_style(mode="tablecaption"))

    def renderCaption(self, table):
        res = []
        for row in table.children[:]:
            if row.__class__ == advtree.Caption:
                res = self.writeCaption(row)
                table.remove_child(
                    row
                )  # this is slight a hack. we do this in order not to simplify cell-coloring code
            elif row.__class__ != advtree.Row:
                table.remove_child(row)
        return res

    def writeCell(self, cell):
        elements = []
        elements.extend(self.renderCell(cell))
        return elements

    def _extraCellPadding(self, cell):
        return (
            cell.get_child_nodes_by_class(advtree.NamedURL)
            or cell.get_child_nodes_by_class(advtree.Reference)
            or cell.get_child_nodes_by_class(advtree.Sup)
        )

    def renderCell(self, cell):
        align = styleutils.get_text_alignment(cell)
        if (
            not align
            and getattr(cell, "is_header", False)
            or all(item.__class__ == advtree.ImageLink for item in cell.children)
        ):
            align = "center"
        elements = []
        if self._extraCellPadding(cell):
            elements.append(Spacer(0, 1))
        if getattr(cell, "is_header", False):
            self.formatter.strong_style += 1
            for c in cell.children:
                c.is_header = True
        elements.extend(
            self.renderMixed(cell, text_style(in_table=self.table_nesting, text_align=align))
        )

        for i, e in enumerate(elements):
            if isinstance(e, str):
                elements[i] = buildPara([e])[0]

        if getattr(cell, "is_header", False):
            self.formatter.strong_style -= 1

        return elements

    def writeRow(self, row):
        r = []
        for cell in row:
            if cell.__class__ == advtree.Cell:
                r.append(self.writeCell(cell))
            else:
                log.warning(
                    "table row contains non-cell node, skipped: %r" % cell.__class__.__name__
                )
        return r

    def _correctWidth(self, element):
        width_correction = 0
        if hasattr(element, "style"):
            width_correction += element.style.leftIndent + element.style.rightIndent
        return width_correction

    def getMinElementSize(self, element):
        try:
            w_min, h_min = element.wrap(0, pdfstyles.page_height)
        except TypeError:  # issue with certain cjk text
            return 0, 0
        min_width = w_min + self._correctWidth(element)
        min_width += 2 * pdfstyles.cell_padding
        return min_width, h_min

    def getMaxParaWidth(self, p, print_width):
        from reportlab.pdfbase.pdfmetrics import stringWidth

        kind = p.blPara.kind
        space_width = stringWidth(" ", p.style.fontName, p.style.fontSize)
        total_width = 0
        current_width = 0
        for line in p.blPara.lines:
            extraspace = line[0] if kind == 0 else line.extraSpace
            line_width = print_width - extraspace
            current_width += line_width
            if getattr(line, "lineBreak", False):
                total_width = max(total_width, current_width)
                current_width = 0
            else:
                current_width += space_width
        total_width = max(total_width, current_width)
        return total_width - space_width

    def getMaxElementSize(self, element, w_min, h_min):
        if element.__class__ == Paragraph:
            element.wrap(pdfstyles.print_width, pdfstyles.print_height)
            pad = 2 * pdfstyles.cell_padding
            width = self.getMaxParaWidth(element, pdfstyles.print_width)
            return width + pad, 0
        w_max, h_max = element.wrap(10 * pdfstyles.page_width, pdfstyles.page_height)
        rows = h_min / h_max if h_max > 0 else 1
        max_width = rows * w_min
        max_width += 2 * rows * pdfstyles.cell_padding
        return max_width, h_max

    def getCurrentColWidth(self, table, cell, col_idx):
        colwidth = sum(table.colwidths[col_idx : col_idx + cell.colspan])
        return colwidth

    def getCellSize(self, elements, cell):
        min_width = 0
        max_width = 0
        for element in elements:
            if element.__class__ == DummyTable:
                pad = 2 * pdfstyles.cell_padding
                return sum(element.min_widths) + pad, sum(element.max_widths) + pad
            w_min, h_min = self.getMinElementSize(element)
            min_width = max(min_width, w_min)
            w_max, h_max = self.getMaxElementSize(element, w_min, h_min)
            max_width = max(max_width, w_max)

        return min_width, max_width

    def _getTableSize(self, t):
        min_widths = [0 for x in range(t.num_cols)]
        max_widths = [0 for x in range(t.num_cols)]
        for row in t.children:
            for col_idx, cell in enumerate(row.children):
                content = self.renderCell(cell)
                min_width, max_width = self.getCellSize(content, cell)
                cell.min_width, cell.max_width = min_width, max_width
                if cell.colspan == 1:
                    min_widths[col_idx] = max(min_width, min_widths[col_idx])
                    max_widths[col_idx] = max(max_width, max_widths[col_idx])
                cell.col_idx = col_idx

        for row in t.children:  # handle colspanned cells
            col_idx = 0
            for cell in row.children:
                if cell.colspan > 1:
                    if cell.min_width > sum(min_widths[col_idx : col_idx + cell.colspan]):
                        for k in range(cell.colspan):
                            min_widths[col_idx + k] = max(
                                cell.min_width / cell.colspan, min_widths[col_idx + k]
                            )
                    if cell.max_width > sum(max_widths[col_idx : col_idx + cell.colspan]):
                        for k in range(cell.colspan):
                            max_widths[col_idx + k] = max(
                                cell.max_width / cell.colspan, max_widths[col_idx + k]
                            )
                col_idx += 1
        return min_widths, max_widths

    def getTableSize(self, t):
        t.min_widths, t.max_widths = self._getTableSize(t)
        table_width = sum(t.min_widths)
        if (table_width > self.getAvailWidth() and self.table_nesting > 1) or (
            table_width
            > (
                pdfstyles.page_width
                - (pdfstyles.page_margin_left + pdfstyles.page_margin_right) / 4
            )
            and self.table_nesting == 1
        ):
            pdfstyles.cell_padding = 2
            total_padding = t.num_cols * pdfstyles.cell_padding
            scale = (pdfstyles.print_width - total_padding) / (sum(t.min_widths) - total_padding)
            log.info("scaling down text in wide table by factor of %.2f" % scale)
            t.rel_font_size = self.formatter.rel_font_size
            self.formatter.set_relative_font_size(scale)
            t.small_table = True
            t.min_widths, t.max_widths = self._getTableSize(t)

    def emptyTable(self, t):
        for row in t.children:
            if row.__class__ == advtree.Row:
                for _ in row.children:
                    return False
        return True

    def writeTable(self, t):
        if self.emptyTable(t):
            return []
        self.table_nesting += 1
        elements = []
        if len(t.children) >= pdfstyles.min_rows_for_break and self.table_nesting == 1:
            elements.append(CondPageBreak(pdfstyles.min_table_space))
        elements.extend(self.renderCaption(t))
        rltables.flip_dir(t, rtl=self.rtl)
        rltables.checkSpans(t)
        t.num_cols = t.numcols
        self.table_size_calc += 1
        if not getattr(t, "min_widths", None) and not getattr(t, "max_widths", None):
            self.getTableSize(t)
        self.table_size_calc -= 1
        if self.table_size_calc > 0:
            self.table_nesting -= 1
            return [DummyTable(t.min_widths, t.max_widths)]
        avail_width = self.getAvailWidth()
        stretch = self.table_nesting == 1 and t.attributes.get("width", "") == "100%"
        t.colwidths = rltables.optimizeWidths(
            t.min_widths, t.max_widths, avail_width, stretch=stretch, table=t
        )
        table_data = []
        for row in t.children:
            row_data = []
            for col_idx, cell in enumerate(row.children):
                self.colwidth = self.getCurrentColWidth(t, cell, col_idx)
                row_data.append(self.write(cell))
            table_data.append(row_data)
        table = Table(table_data, colWidths=t.colwidths, splitByRow=1)
        table.setStyle(rltables.getStyles(t))
        table.hAlign = pdfstyles.table_align
        if table_style.get("spaceBefore", 0) > 0:
            elements.append(Spacer(0, table_style["spaceBefore"]))
        elements.append(table)
        if table_style.get("spaceAfter", 0) > 0:
            elements.append(Spacer(0, table_style["spaceAfter"]))
        self.table_nesting -= 1
        if self.table_nesting == 0:
            self.colwidth = 0
        if getattr(t, "small_table", False):
            pdfstyles.cell_padding = 3
            self.formatter.set_relative_font_size(t.rel_font_size)
        return elements

    def addAnchors(self, table):
        anchors = ""
        for article_id in self.articleids:
            newAnchor = '<a name="%s" />' % article_id
            anchors = f"{anchors}{newAnchor}"
        p = Paragraph(anchors, text_style())

        c = table._cellvalues[0][0]
        if not c:
            c = [p]
        else:
            c.append(p)

    def delAnchors(self, table):
        c = table._cellvalues[0][0]
        if c:
            c.pop()

    def writeMath(self, node):
        source = re.compile("\n+").sub(
            "\n", node.caption.strip()
        )  # remove multiple newlines, as this could break the mathRenderer
        if not len(source):
            return []
        if source.endswith("\\"):
            source += " "

        try:
            density = int(os.environ.get("MATH_RESOLUTION", "120"))
        except ValueError:
            density = 120  # resolution in dpi in which math images are rendered by texvc

        imgpath = None

        def has_cache():
            return self.math_cache_dir and os.path.isdir(self.math_cache_dir)

        if has_cache():
            _md5 = md5()
            _md5.update(source.encode("utf-8"))
            math_id = _md5.hexdigest()
            cached_path = os.path.join(
                self.math_cache_dir, f"{math_id[0]}/{math_id[1]}/{math_id}-{density}.png"
            )
            if os.path.exists(cached_path):
                imgpath = cached_path

        if not imgpath:
            imgpath = writerbase.renderMath(
                source,
                output_path=self.tmpdir,
                output_mode="png",
                render_engine="texvc",
                resolution_in_dpi=density,
            )
            if not imgpath:
                return []
            if has_cache():
                if not os.path.isdir(os.path.dirname(cached_path)):
                    os.makedirs(os.path.dirname(cached_path))
                shutil.move(imgpath, cached_path)
                imgpath = cached_path

        img = PilImage.open(imgpath)
        if self.debug:
            log.info("math png at:", imgpath)
        w, h = img.size
        del img

        if w > pdfstyles.max_math_width or h > pdfstyles.max_math_height:
            log.info("skipping math formula, png to big: %r, w:%d, h:%d" % (source, w, h))
            return ""
        if self.table_nesting:  # scale down math-formulas in tables
            w = w * pdfstyles.small_font_size / pdfstyles.font_size
            h = h * pdfstyles.small_font_size / pdfstyles.font_size

        scale = (self.getAvailWidth()) / (w / density * 72)
        if scale < 1:
            w *= scale
            h *= scale

        # the vertical image placement is calculated below:
        # the "normal" height of a single-line formula is 17px
        imgAlign = "%fin" % (-(h - 15) / (2 * density))
        # the non-breaking-space is needed to force whitespace after the formula
        return [
            '<img src="{path}" width="{width:f}pt" height="{height:f}pt" valign="{valign}" />'.format(
                path=imgpath.encode(sys.getfilesystemencoding()),
                width=w / density * 72,
                height=h / density * 72,
                valign=imgAlign,
            )
        ]

    def writeTimeline(self, node):
        img_path = timeline.draw_timeline(node.timeline, self.tmpdir)
        if img_path:
            # width and height should be parsed by the....parser and not guessed by the writer
            node.width = 180
            node.thumb = True
            node.isInline = lambda: False
            w, h = self.image_utils.get_image_size(node, img_path)
            return [Figure(img_path, "", text_style(), imgWidth=w, imgHeight=h)]
        return []

    writeControl = ignore
    writeVar = writeEmphasized


def writer(
    env,
    output,
    status_callback=None,
    coverimage=None,
    strict=False,
    debug=False,
    mathcache=None,
    lang=None,
    profile=None,
):
    r = RlWriter(env, strict=strict, debug=debug, mathcache=mathcache, lang=lang)
    if coverimage is None and env.configparser.has_section("pdf"):
        coverimage = env.configparser.get("pdf", "coverimage", None)

    if profile:
        import cProfile

        cProfile.runctx(
            "r.writeBook(output=output, coverimage=coverimage, status_callback=status_callback)",
            globals(),
            locals(),
            os.path.expanduser(profile),
        )
    else:
        r.writeBook(output=output, coverimage=coverimage, status_callback=status_callback)


writer.description = "PDF documents (using ReportLab)"
writer.content_type = "application/pdf"
writer.file_extension = "pdf"
writer.options = {
    "coverimage": {
        "param": "FILENAME",
        "help": "filename of an image for the cover page",
    },
    "strict": {
        "help": "raise exception if errors occur",
    },
    "debug": {
        "help": "debugging mode is more verbose",
    },
    "mathcache": {
        "param": "DIRNAME",
        "help": "directory of cached math images",
    },
    "lang": {
        "param": "LANGUAGE",
        "help": 'use translated strings in given language (defaults to "en" for English)',
    },
    "profile": {
        "param": "PROFILEFN",
        "help": "profile run time. ONLY for debugging purposes",
    },
}
