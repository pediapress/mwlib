#! /usr/bin/env python

# Copyright (c) 2007, PediaPress GmbH
# See README.txt for additional licensing information.

import copy
import cProfile
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

from mwlib.tree import advtree

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
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus.doctemplate import (
    BaseDocTemplate,
    NextPageTemplate,
    NotAtTopPageBreak,
)
from reportlab.platypus.flowables import CondPageBreak, HRFlowable, PageBreak, Spacer
from reportlab.platypus.paragraph import Paragraph
from reportlab.platypus.tables import Table
from reportlab.platypus.xpreformatted import XPreformatted

from mwlib import parser, timeline, writerbase
from mwlib._version import version as mwlibversion
from mwlib.mw_math.mathutils import render_math
from mwlib.parser import URL, Caption, NamedURL
from mwlib.refine import uparser
from mwlib.tree.treecleaner import TreeCleaner
from mwlib.utilities import log
from mwlib.writer import miscutils, styleutils
from mwlib.writer.imageutils import ImageUtils
from mwlib.writer.licensechecker import LicenseChecker
from mwlib.writers.rl._version import VERSION as rlwriterversion
from mwlib.writers.rl.customflowables import (
    DummyTable,
    Figure,
    FiguresAndParagraphs,
    SmartKeepTogether,
    TocEntry,
)
from mwlib.writers.rl.customnodetransformer import CustomNodeTransformer
from mwlib.writers.rl.formatter import RLFormatter
from mwlib.writers.rl.toc import TocRenderer

from . import fontconfig, pdfstyles, rltables
from .pagetemplates import PPDocTemplate, TitlePage, WikiPage
from .pdfstyles import (
    PRINT_HEIGHT,
    PRINT_WIDTH,
    TABLE_STYLE,
    heading_style,
    text_style,
)
from .rlsourceformatter import ReportlabFormatter
from .utils import build_paragraph, check_reportlab, is_inline

with contextlib.suppress(ImportError):
    from mwlib import _extversion


try:
    from mwlib import linuxmem
except ImportError:
    linuxmem = None


check_reportlab()


log = log.Log("rlwriter")


class ReportlabError(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class RlWriter:
    def __init__(
        self,
        env=None,
        strict=False,
        debug=False,
        mathcache=None,
        lang=None,
        test_mode=False,
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
        pdfstyles.DEFAULT_LATIN_FONT = pdfstyles.DEFAULT_FONT
        self.word_wrap = None
        if lang in ["ja", "ch", "ko", "zh"]:
            self.word_wrap = "CJK"
            pdfstyles.WORD_WRAP = self.word_wrap
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
                pdfstyles.DEFAULT_FONT = arabic_font
                pdfstyles.SERIF_FONT = arabic_font
                pdfstyles.SANS_FONT = arabic_font
            rl_config.rtl = True

        self.env = env
        if self.env is not None:
            self.book = self.env.metabook
            self.img_db = env.images
        else:
            self.img_db = None

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
            self.license_checker = LicenseChecker(
                image_db=self.img_db, filter_type="whitelist"
            )
        else:
            self.license_checker = LicenseChecker(
                image_db=self.img_db, filter_type="blacklist"
            )
        self.license_checker.read_licenses_csv()

        self.img_meta_info = {}
        self.img_count = 0

        self.font_switcher.font_paths = fontconfig.font_paths
        self.font_switcher.register_default_font(pdfstyles.DEFAULT_FONT)
        self.font_switcher.register_font_def_list(fontconfig.fonts)
        self.font_switcher.register_reportlab_fonts(fontconfig.fonts)

        self.tree_cleaner = TreeCleaner([], save_reports=self.debug, rtl=self.rtl)
        self.tree_cleaner.skip_methods = pdfstyles.TREE_CLEANER_SKIP_METHODS
        self.tree_cleaner.content_without_text_classes.append(advtree.ReferenceList)

        self.cnt = CustomNodeTransformer()
        self.formatter = RLFormatter(font_switcher=self.font_switcher)

        self.image_utils = ImageUtils(
            pdfstyles.PRINT_WIDTH,
            pdfstyles.PRINT_HEIGHT,
            pdfstyles.IMG_DEFAULT_THUMB_WIDTH,
            pdfstyles.IMG_MIN_RES,
            pdfstyles.IMG_MAX_THUMG_WIDTH,
            pdfstyles.IMG_MAX_THUMG_HEIGHT,
            pdfstyles.IMG_INLINE_SCALE_FACTOR,
            pdfstyles.PRINT_WIDTH_PX,
        )

        self.references = []
        self.ref_name_map = {}
        self.list_indentation = 0  # nesting level of lists
        self.list_counter_id = 1
        self.tmp_images = set()
        self.named_link_count = 1
        self.table_nesting = 0
        self.table_size_calc = 0
        self.tablecount = 0
        self.para_indent_level = 0

        self.gallery_mode = False
        self.ref_mode = False
        self.license_mode = False
        self.inline_mode = 0

        self.link_list = []
        self.disable_group_elements = False
        self.fail_safe_rendering = False

        self.current_col_count = 0
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
        self.numarticles = 0
        self.render_status = None

    def ignore(self, _):
        return []

    def _append_element_to_group_or_list(
        self, is_heading, elements, group, grouped_elements
    ):
        if is_heading(elements[0]):
            group.append(elements.pop(0))
        else:
            grouped_elements.append(elements.pop(0))

    def _group_elements_by_heading_and_height(
        self, group, is_heading, elements, grouped_elements, group_height
    ):
        if not group:
            self._append_element_to_group_or_list(
                is_heading, elements, group, grouped_elements
            )
        else:
            last = group[-1]
            if not is_heading(last):
                try:
                    _, height = last.wrap(PRINT_WIDTH, PRINT_HEIGHT)
                except:
                    height = 0
                group_height += height
                if group_height > PRINT_HEIGHT / 10 or isinstance(
                    elements[0], NotAtTopPageBreak
                ):  # 10 % of page_height
                    grouped_elements.append(SmartKeepTogether(group))
                    group = []
                    group_height = 0
                else:
                    group.append(elements.pop(0))
            else:
                group.append(elements.pop(0))
        return group, elements, grouped_elements, group_height

    def groupElements(self, elements):
        """Group reportlab flowables into KeepTogether flowables
        to achieve meaningful pagebreaks

        @type elements: [reportlab.platypus.flowable.Flowable]
        @rtype: [reportlab.platypus.flowable.Flowable]
        """
        grouped_elements = []
        group = []

        def is_heading(element):
            return isinstance(element, HRFlowable) or (
                hasattr(element, "style")
                and element.style.name.startswith("heading_style")
            )

        group_height = 0
        while elements:
            (
                group,
                elements,
                grouped_elements,
                group_height,
            ) = self._group_elements_by_heading_and_height(
                group, is_heading, elements, grouped_elements, group_height
            )
        if group:
            grouped_elements.append(SmartKeepTogether(group))

        return grouped_elements

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
            pdfstyles.WORD_WRAP = "RTL"
        else:
            pdfstyles.WORD_WRAP = self.word_wrap

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
                return CondPageBreak(min_percent / 100.0 * pdfstyles.PRINT_HEIGHT)
        return None

    def write(self, obj):
        method_name = "write" + obj.__class__.__name__
        if not hasattr(self, method_name):
            log.error("unknown node:", repr(obj.__class__.__name__))
            if self.strict:
                raise writerbase.WriterError(
                    "Unkown Node: %s " % obj.__class__.__name__
                )
            return []
        method = getattr(self, method_name)
        styles = self.formatter.set_style(obj)
        original = self.check_direction(obj)
        res = method(obj)
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
        art = mywiki.get_parsed_article(title=item.title, revision=item.revision)
        if not art:
            return  # FIXME
        try:
            namespace = item.wiki.normalize_and_get_page(item.title, 0).ns
        except AttributeError:
            namespace = 0
        art.ns = namespace
        art.url = mywiki.get_url(item.title, item.revision) or None
        if item.displaytitle is not None:
            art.caption = item.displaytitle
        source = mywiki.get_source(item.title, item.revision)
        if source:
            art.wikiurl = source.url or ""
        else:
            art.wikiurl = None
        art.authors = mywiki.get_authors(item.title, revision=item.revision)
        advtree.build_advanced_tree(art)
        if self.debug:
            parser.show(sys.stdout, art)
            pass
        self.tree_cleaner.tree = art
        self.tree_cleaner.clean_all()
        self.cnt.transform_css(art)
        if self.debug:
            # parser.show(sys.stdout, art)
            print("\n".join([repr(r) for r in self.tree_cleaner.get_reports()]))
        return art

    def initReportlabDoc(self, output):
        version = self.getVersion()
        toc_callback = self.toc_callback if pdfstyles.RENDER_TOC else None
        self.doc = PPDocTemplate(
            output,
            topMargin=pdfstyles.PAGE_MARGIN_TOP,
            leftMargin=pdfstyles.PAGE_MARGIN_LEFT,
            rightMargin=pdfstyles.PAGE_MARGIN_RIGHT,
            bottomMargin=pdfstyles.PAGE_MARGIN_BOTTOM,
            title=self.book.title,
            keywords=version,
            status_callback=self.render_status,
            toc_callback=toc_callback,
        )

    def articleRenderingOK(self, node, output):
        testdoc = BaseDocTemplate(
            output,
            topMargin=pdfstyles.PAGE_MARGIN_TOP,
            leftMargin=pdfstyles.PAGE_MARGIN_LEFT,
            rightMargin=pdfstyles.PAGE_MARGIN_RIGHT,
            bottomMargin=pdfstyles.PAGE_MARGIN_BOTTOM,
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
            trace = traceback.format_exc()
            log.error(trace)
            self.doc = doc_bak
            return False

    def addDummyPage(self):
        wiki_page = WikiPage("")
        self.doc.addPageTemplates(wiki_page)
        return Paragraph(" ", text_style())

    def writeBook(self, output, coverimage=None, status_callback=None):
        self.numarticles = len(self.env.metabook.articles())
        self.articlecount = 0
        self.getArticleIDs()

        if status_callback:
            self.layout_status = status_callback.get_sub_range(1, 75)
            self.layout_status(status="laying out")
            self.render_status = status_callback.get_sub_range(76, 100)
        else:
            self.layout_status = None
            self.render_status = None
        self.initReportlabDoc(output)

        elements = []
        self.toc_entries = []
        if pdfstyles.SHOW_TITLE_PAGE:
            elements.extend(
                self.writeTitlePage(coverimage=coverimage or pdfstyles.TITLE_PAGE_IMAGE)
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
                self.img_db = item.images
                self.license_checker.image_db = self.img_db
                if not art:
                    continue
                if got_chapter:
                    art.has_preceeding_chapter = True
                    got_chapter = False
                if self.fail_safe_rendering and not self.articleRenderingOK(
                    copy.deepcopy(art), output
                ):
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
                raise RuntimeError("Giving up.") from err
            self.fail_safe_rendering = True
            self.writeBook(
                output, coverimage=coverimage, status_callback=status_callback
            )

    def _append_metadata_and_references_to_elements(self, elements):
        elements.append(TocEntry(txt=_("References"), lvl="group"))
        elements.append(self._get_page_template(_("Article Sources and Contributors")))
        elements.append(NotAtTopPageBreak())
        elements.extend(self.writeArticleMetainfo())
        elements.append(
            self._get_page_template(_("Image Sources, Licenses and Contributors"))
        )
        if self.numarticles > 1:
            elements.append(NotAtTopPageBreak())
        elements.extend(self.writeImageMetainfo())

    def renderBook(self, elements, output):
        if pdfstyles.SHOW_ARTICLE_ATTRIBUTION:
            self._append_metadata_and_references_to_elements(elements)

        if not self.debug:
            elements.extend(self.renderLicense())

        self.render_status(status="rendering", article="")

        if not self.fail_safe_rendering:
            self.doc.bookmarks = self.bookmarks

        # debughelper.dump_elements(elements)

        log.info("start rendering: %r" % output)

        try:
            gc.collect()
            if linuxmem:
                log.info("memory usage after laying out:", linuxmem.memory())
            self.doc.build(elements)
            if pdfstyles.RENDER_TOC and self.numarticles > 1:
                err = self.toc_renderer.build(
                    output,
                    self.toc_entries,
                    has_title_page=bool(self.book.title),
                    rtl=self.rtl,
                )
                if err:
                    log.warning(
                        f"TOC not rendered. Probably pdftk is not properly installed. returncode: {err}"
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
        if not pdfstyles.SHOW_WIKI_LICENSE:
            return []
        if self.env.get_licenses():
            elements.append(TocEntry(txt=_("Article Licenses"), lvl="group"))

        for license in self.env.get_licenses():
            license_node = uparser.parse_string(
                title=_(license.title), raw=license.wikitext, wikidb=license._wiki
            )
            advtree.build_advanced_tree(license_node)
            self.tree_cleaner.tree = license_node
            self.tree_cleaner.clean_all()
            elements.extend(self.writeArticle(license_node))
        self.license_mode = False
        return elements

    def getArticleIDs(self):
        self.articleids = []
        for item in self.env.metabook.walk():
            if item.type != "article":
                continue
            title = item.displaytitle or item.title

            source = item.wiki.get_source(item.title, item.revision)
            wikiurl = source.url if source else item.title
            article_id = self.buildArticleID(wikiurl, title)
            self.articleids.append(article_id)

    def toc_callback(self, info):
        self.toc_entries.append(info)

    def writeTitlePage(self, coverimage=None):
        # FIXME: clean this up. there seems to be quite a bit of deprecated here
        title = self.book.title
        subtitle = self.book.subtitle

        if not title:
            return []
        first_article_title = None
        for item in self.book.walk():
            if (
                item.type == "Chapter"
            ):  # dont set page header if pdf starts with a chapter
                break
            if item.type == "article":
                first_article_title = self.renderArticleTitle(
                    item.displaytitle or item.title
                )
                break
        self.doc.addPageTemplates(TitlePage(cover=coverimage))
        elements = []
        elements.append(
            Paragraph(self.formatter.clean_text(title), text_style(mode="booktitle"))
        )
        if subtitle:
            elements.append(
                Paragraph(
                    self.formatter.clean_text(subtitle), text_style(mode="booksubtitle")
                )
            )
        if not first_article_title:
            return elements
        self.doc.addPageTemplates(WikiPage(first_article_title, rtl=self.rtl))
        elements.append(NextPageTemplate(first_article_title))
        elements.append(PageBreak())
        return elements

    def _get_page_template(self, title):
        template_title = self.renderArticleTitle(title)
        page_template = WikiPage(template_title, rtl=self.rtl)
        self.doc.addPageTemplates(page_template)
        return NextPageTemplate(template_title)

    def writeChapter(self, chapter):
        horizontal_rule = HRFlowable(
            width="80%",
            spaceBefore=6,
            spaceAfter=0,
            color=pdfstyles.CHAPTER_RULE_COLOR,
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

        elements.append(self._get_page_template(""))
        elements.extend(
            [NotAtTopPageBreak(), horizontal_rule, chapter_para, horizontal_rule]
        )
        elements.append(TocEntry(txt=title, lvl="Chapter"))
        elements.append(self._get_page_template(chapter.next_article_title))
        elements.extend(self.renderChildren(chapter))

        return elements

    def writeSection(self, obj):
        lvl = getattr(obj, "level", 4)
        if self.license_mode:
            new_heading_style = heading_style("License")
        else:
            new_heading_style = heading_style("section", lvl=lvl + 1)
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
                f'<font name="{new_heading_style.fontName}"><b>{heading_txt}</b></font>{anchor}',
                new_heading_style,
            )
        ]

        if self.table_size_calc == 0:
            obj.remove_child(obj.children[0])
        elements.extend(self.renderMixed(obj))

        return elements

    def renderFailedNode(self, node, info_text):
        txt = node.get_all_display_text()
        txt = xmlescape(txt)
        elements = []
        elements.extend(
            [
                Spacer(0, 1 * cm),
                HRFlowable(width="100%", thickness=2),
                Spacer(0, 0.5 * cm),
            ]
        )
        elements.append(Paragraph(info_text, text_style(in_table=False)))
        elements.append(Spacer(0, 0.5 * cm))
        elements.append(Paragraph(txt, text_style(in_table=False)))
        elements.extend(
            [
                Spacer(0, 0.5 * cm),
                HRFlowable(width="100%", thickness=2),
                Spacer(0, 1 * cm),
            ]
        )
        return elements

    def buildArticleID(self, wikiurl, article_name):
        tmplink = advtree.Link()
        tmplink.target = article_name
        tmplink.capitalize_target = True  # this is a hack, this info should pulled out of the environment if available
        # tmplink._normalizeTarget() # FIXME: this is currently removed from mwlib. we need to check URL handling in mwlib
        idstr = f"{wikiurl}{tmplink.target}"
        md_hash = md5(idstr.encode("utf-8"))
        return md_hash.hexdigest()

    def _filter_anon_ip_edits(self, authors):
        if authors:
            authors_text = ", ".join([a for a in authors if a != "ANONIPEDITS:0"])
            authors_text = re.sub(
                r"ANONIPEDITS:(?P<num>\d+)",
                r"\g<num> %s" % _("anonymous edits"),
                authors_text,
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
            authors_text = self._filter_anon_ip_edits(authors)
            txt = "<b>{title}</b> &nbsp;<i>{source_label}</i>: {source} &nbsp;<i>{contribs_label}</i>: {contribs} ".format(
                title=title,
                source_label=self.formatter.clean_text(_("Source")),
                source=self.formatter.clean_text(url),
                contribs_label=self.formatter.clean_text(_("Contributors")),
                contribs=authors_text,
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
            authors_text = self._filter_anon_ip_edits(authors)
            if not license:
                license = _("unknown")
            license_txt = "<i>{license_label}</i>: {license} &nbsp;".format(
                license_label=self.formatter.clean_text(_("License")),
                license=self.formatter.clean_text(license),
            )
            txt = "<b>{title}</b> &nbsp;<i>{source_label}</i>: {source} &nbsp;{license_txt}<i>{contribs_label}</i>: {contribs} ".format(
                title=self.formatter.clean_text(title),
                source_label=self.formatter.clean_text(_("Source")),
                source=self.formatter.clean_text(url),
                license_txt=license_txt,
                contribs_label=self.formatter.clean_text(_("Contributors")),
                contribs=authors_text,
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
            for child in node.children:
                self.cleanTitle(child)

    def renderArticleTitle(self, raw):
        title_node = uparser.parse_string(title="", raw=raw, expand_templates=False)
        advtree.build_advanced_tree(title_node)
        title_node.__class__ = advtree.Node
        self.cleanTitle(title_node)
        res = self.renderInline(title_node)
        return "".join(res)

    def _append_title_and_conditional_page_breaks(self, elements, title, article):
        elements.append(self._get_page_template(title))
        # FIXME remove the getPrevious below
        if self.license_mode:
            if self.numarticles > 1:
                elements.append(NotAtTopPageBreak())
        elif not getattr(article, "has_preceeding_chapter", False) or isinstance(
            article.get_previous(), advtree.Article
        ):
            if (
                pdfstyles.PAGE_BREAK_AFTER_ARTICLE
            ):  # if configured and preceded by an article
                elements.append(NotAtTopPageBreak())
            elif miscutils.article_starts_with_infobox(
                article, max_text_until_infobox=100
            ):
                elements.append(
                    CondPageBreak(pdfstyles.ARTICLE_START_MIN_SPACE_INFOBOX)
                )
            else:
                elements.append(CondPageBreak(pdfstyles.ARTICLE_START_MIN_SPACE))

    def _append_references_and_update_metadata(self, elements, title, article, url):
        if self.references:
            ref_elements = [
                Paragraph(
                    "<b>" + _("References") + "</b>", heading_style("section", lvl=3)
                )
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
            self._append_title_and_conditional_page_breaks(elements, title, article)
        if self.inline_mode == 0 and self.table_nesting == 0:
            heading_anchor = '<a name="%d"/>' % len(self.bookmarks)
            self.bookmarks.append((article.caption, "article"))
        else:
            heading_anchor = ""

        # add anchor for internal links
        url = getattr(article, "url", None)
        if url:
            article_id = self.buildArticleID(article.wikiurl, article.caption)
            heading_anchor = "{}{}".format(
                heading_anchor, '<a name="%s" />' % article_id
            )
        else:
            article_id = None

        heading_para = Paragraph(
            f"<b>{title}</b>{heading_anchor}", heading_style("article")
        )
        elements.append(heading_para)
        elements.append(TocEntry(txt=title, lvl="article"))

        if pdfstyles.SHOW_ARTICLE_HR:
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
            article_fail_text = _(
                "<strong>WARNING: Article could not be rendered - outputting plain text.</strong><br/>Potential causes of the problem are: (a) a bug in the pdf-writer software (b) problematic Mediawiki markup (c) table is too wide"
            )
            elements.extend(self.renderFailedNode(article, article_fail_text))

        # check for non-flowables
        elements = [e for e in elements if not isinstance(e, str)]
        elements = self.floatImages(elements)
        elements = self.tabularizeImages(elements)

        self._append_references_and_update_metadata(elements, title, article, url)

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

    def got_sufficient_floats(self, figures, paras):
        total_figure_height = 0
        total_paragraph_height = 0
        max_img_width = 0
        for figure in figures:
            # assume 40 chars per line for caption text
            total_figure_height += (
                figure.imgHeight
                + figure.margin[0]
                + figure.margin[2]
                + figure.padding[0]
                + figure.padding[2]
                + figure.cs.leading * max(int(len(figure.captionTxt) / 40), 1)
            )
            max_img_width = max(max_img_width, figure.imgWidth)
        for paragraph in paras:
            if isinstance(paragraph, Paragraph):
                _, height = paragraph.wrap(PRINT_WIDTH - max_img_width, PRINT_HEIGHT)
                height += paragraph.style.spaceBefore + paragraph.style.spaceAfter
                total_paragraph_height += height
        return total_paragraph_height > total_figure_height - 10

    def _handle_floating_nodes_and_figures(
        self, node, combined_nodes, figures, floating_nodes
    ):
        if (
            hasattr(floating_nodes[-1], "style")
            and floating_nodes[-1].style.name.startswith("heading_style")
            and floating_nodes[-1].style.flowable is True
        ):  # prevent floating headings before nonFloatables
            no_float_node = floating_nodes[-1]
            floating_nodes = floating_nodes[:-1]
        else:
            no_float_node = None
        if len(floating_nodes) == 0:
            combined_nodes.extend(figures)
            figures = []
            combined_nodes.append(no_float_node)
            if getattr(node, "float_figure", False):
                figures.append(node)
            else:
                combined_nodes.append(node)
            last_node = node
            return last_node, combined_nodes, figures, floating_nodes, True
        figure_margin = self.get_margins(figures[0].align or "right")
        combined_nodes.append(
            FiguresAndParagraphs(
                figures,
                floating_nodes,
                figure_margin=figure_margin,
                rtl=self.rtl,
            )
        )
        if no_float_node:
            combined_nodes.append(no_float_node)
        figures = []
        floating_nodes = []
        if getattr(node, "float_figure", False):
            figures.append(node)
        else:
            combined_nodes.append(node)
        return figures, floating_nodes, False

    def _append_node_to_appropriate_list(self, node, figures, combined_nodes):
        if getattr(node, "float_figure", False):
            figures.append(node)
        else:
            combined_nodes.append(node)

    def _organize_and_combine_figure_and_floating_nodes(
        self, node, combined_nodes, figures, floating_nodes
    ):
        if not figures:
            self._append_node_to_appropriate_list(node, figures, combined_nodes)
        else:
            if (
                hasattr(node, "style")
                and node.style.flowable is True
                and not self.got_sufficient_floats(figures, floating_nodes)
            ):  # newpara
                floating_nodes.append(node)
            else:
                if floating_nodes:
                    (
                        figures,
                        floating_nodes,
                        should_continue,
                    ) = self._handle_floating_nodes_and_figures(
                        node, combined_nodes, figures, floating_nodes
                    )
                    if should_continue:
                        return node, combined_nodes, figures, floating_nodes, True
                else:
                    combined_nodes.extend(figures)
                    combined_nodes.append(node)
                    figures = []
        return node, combined_nodes, figures, floating_nodes, False

    def get_margins(self, align):
        if align == "right":
            return pdfstyles.IMG_MARGINS_FLOAT_RIGHT
        elif align == "left":
            return pdfstyles.IMG_MARGINS_FLOAT_LEFT
        return pdfstyles.IMG_MARGINS_FLOAT

    def _combine_figures_and_floating_nodes(
        self, figures, floating_nodes, combined_nodes
    ):
        if figures and floating_nodes:
            figure_margin = self.get_margins(figures[0].align or "right")
            combined_nodes.append(
                FiguresAndParagraphs(
                    figures, floating_nodes, figure_margin=figure_margin, rtl=self.rtl
                )
            )
        else:
            combined_nodes.extend(figures + floating_nodes)

    def floatImages(self, nodes):
        """Floating images are combined with paragraphs.
        This is achieved by sticking images and paragraphs
        into a FiguresAndParagraphs flowable

        @type nodes: [reportlab.platypus.flowable.Flowable]
        @rtype: [reportlab.platypus.flowable.Flowable]
        """

        combined_nodes = []
        floating_nodes = []
        figures = []
        last_node = None

        for node in nodes:  # FIXME: somebody should clean up this mess
            if isinstance(last_node, Figure) and isinstance(node, Figure):
                if getattr(node, "float_figure", False):
                    figures.append(node)
                else:
                    combined_nodes.extend(figures)
                    combined_nodes.extend([Spacer(0, 0.5 * cm), node])
                    figures = []
            else:
                (
                    node,
                    combined_nodes,
                    figures,
                    floating_nodes,
                    should_continue,
                ) = self._organize_and_combine_figure_and_floating_nodes(
                    node, combined_nodes, figures, floating_nodes
                )
                if should_continue:
                    continue

            last_node = node

        self._combine_figures_and_floating_nodes(
            figures, floating_nodes, combined_nodes
        )

        return combined_nodes

    def _scale_images(self, images):
        scaled_images = []
        for img in images:
            aspect_ratio = img.imgWidth / img.imgHeight
            width = PRINT_WIDTH / 2 - (
                img.margin[1] + img.margin[3] + img.padding[1] + img.padding[3]
            )
            height = width / aspect_ratio
            if width > img.imgWidth:
                scaled = img
            else:
                scaled = Figure(
                    img.img_path,
                    img.captionTxt,
                    img.cs,
                    img_width=width,
                    img_height=height,
                    margin=img.margin,
                    padding=img.padding,
                    border_color=img.borderColor,
                    url=img.url,
                )
            scaled_images.append(scaled)
        return scaled_images

    def _arrange_and_append_figures(self, figures, final_nodes, node):
        should_clear_figures = False
        if len(figures) > 1:
            figures = self._scale_images(figures)
            data = [
                [figures[2 * i], figures[2 * i + 1]]
                for i in range(int(len(figures) / 2))
            ]
            if len(figures) % 2 != 0:
                data.append([figures[-1], ""])
            table = Table(data)
            final_nodes.append(table)
            figures = []
        else:
            if figures:
                final_nodes.append(figures[0])
                figures = []
                should_clear_figures = True
            final_nodes.append(node)
        return should_clear_figures

    def tabularizeImages(self, nodes):
        """consecutive images that couldn't be combined with paragraphs
        are put into a 2 column table
        """
        final_nodes = []
        figures = []

        for node in nodes:
            if isinstance(node, Figure):
                figures.append(node)
            else:
                should_clear_figures = self._arrange_and_append_figures(
                    figures, final_nodes, node
                )
                if should_clear_figures:
                    figures = []
        if len(figures) > 1:
            figures = self._scale_images(figures)
            data = [
                [figures[2 * i], figures[2 * i + 1]]
                for i in range(int(len(figures) / 2))
            ]
            if len(figures) % 2 != 0:
                data.append([figures[-1], ""])
            table = Table(data)
            final_nodes.append(table)
        else:
            final_nodes.extend(figures)
        return final_nodes

    def writePreFormatted(self, obj):
        self.formatter.pre_mode = True
        rtl, self.rtl = self.rtl, False
        txt = self.renderInline(obj)
        self.rtl = rtl
        text = "".join(txt)
        text = re.sub("<br */>", "\n", text)
        text = text.replace("\t", " " * pdfstyles.TABSIZE)
        self.formatter.pre_mode = False
        if not text:
            return []

        avail_width = self.getAvailWidth()
        width = None
        style = text_style(mode="preformatted", in_table=self.table_nesting)
        while not width or width > avail_width:
            pre = XPreformatted(text, style)
            width, _ = pre.wrap(avail_width, pdfstyles.PAGE_HEIGHT)
            style.fontSize -= 0.5
            if style.fontSize < pdfstyles.MIN_PREFORMATTED_SIZE:
                style = text_style(mode="preformatted", in_table=self.table_nesting)
                char_limit = max(
                    1,
                    int(
                        pdfstyles.SOURCE_MAX_LINE_LEN
                        / (max(1, 0.75 * self.current_col_count))
                    ),
                )
                text = self.breakLongLines(text, char_limit)
                pre = XPreformatted(text, style)
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
            if is_inline(res):
                txt.extend(res)
            else:
                log.warning(
                    node.__class__.__name__,
                    " contained block element: ",
                    child.__class__.__name__,
                )
                txt.append(self.renderText(child.get_all_display_text()))
        self.inline_mode -= 1

        text_color = styleutils.rgb_color_from_node(node)
        if text_color:
            hex_col = "".join("%02x" % int(c * 255) for c in text_color)
            txt.insert(0, '<font color="#%s">' % hex_col)
            txt.append("</font>")
        return txt

    def _apply_node_style_to_paragraph(self, node, para_style):
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

    def _process_node_and_generate_styled_items(self, node, items, para_style, txt):
        txt_style = None
        if node.__class__ == advtree.Cell and getattr(node, "is_header", False):
            txt_style = {  # check nesting: start: <a>,<b> --> end: </b></a>
                "start": ["<b>"],
                "end": ["</b>"],
            }
        for child in node:
            res = self.write(child)
            if is_inline(res):
                txt.extend(res)
            else:
                items.extend(build_paragraph(txt, para_style, txt_style=txt_style))
                items.extend(res)
                txt = []
        if not len(items):
            return build_paragraph(txt, para_style, txt_style=txt_style)
        else:
            items.extend(build_paragraph(txt, para_style, txt_style=txt_style))
            return items

    def renderMixed(self, node, para_style=None, text_prefix=None):
        if not para_style:
            if self.license_mode:
                para_style = text_style("License")
            else:
                para_style = text_style(
                    indent_lvl=self.para_indent_level, in_table=self.table_nesting
                )
        elif self.license_mode:
            para_style.fontSize = max(
                text_style("License").fontSize, para_style.fontSize - 4
            )
            para_style.leading = 1

        math_nodes = node.get_child_nodes_by_class(advtree.Math)
        if math_nodes:
            max_source_len = max([len(math.caption) for math in math_nodes])
            if max_source_len > pdfstyles.NO_FLOAT_MATH_LEN:
                para_style.flowable = False

        txt = []
        if text_prefix:
            txt.append(text_prefix)
        items = []

        if isinstance(
            node, advtree.Node
        ):  # set node styles like text/bg colors, alignment
            self._apply_node_style_to_paragraph(node, para_style)

        return self._process_node_and_generate_styled_items(
            node, items, para_style, txt
        )

    def renderChildren(self, node):
        items = []
        for child in node:
            items.extend(self.write(child))
        return items

    def writeEmphasized(self, node):
        return self.renderInline(node)

    def writeStrong(self, node):
        return self.renderInline(node)

    def writeDefinitionList(self, node):
        return self.renderChildren(node)

    def writeDefinitionTerm(self, node):
        txt = self.writeStrong(node)
        return [Paragraph("".join(txt), text_style(in_table=self.table_nesting))]

    def writeDefinitionDescription(self, node):
        return self.writeIndented(node)

    def writeIndented(self, node):
        self.para_indent_level += getattr(node, "indentlevel", 1)
        items = self.renderMixed(
            node,
            para_style=text_style(
                indent_lvl=self.para_indent_level, in_table=self.table_nesting
            ),
        )
        self.para_indent_level -= getattr(node, "indentlevel", 1)
        return items

    def writeBlockquote(self, node):
        self.para_indent_level += 1
        items = self.renderMixed(
            node, text_style(mode="blockquote", in_table=self.table_nesting)
        )
        self.para_indent_level -= 1
        return items

    def writeOverline(self, node):
        # FIXME: there is no way to do overline in reportlab paragraphs.
        return self.renderInline(node)

    def writeUnderline(self, node):
        return self.renderInline(node)

    writeInserted = writeUnderline

    def writeAbbreviation(self, node):
        self.formatter.underline_style += 1
        res = self.renderInline(node)
        self.formatter.underline_style -= 1
        return res

    def writeSub(self, node):
        return self.renderInline(node)

    def writeSup(self, node):
        return self.renderInline(node)

    def writeSmall(self, node):
        return self.renderInline(node)

    def writeBig(self, node):
        return self.renderInline(node)

    def writeCite(self, node):
        return self.writeEmphasized(node)

    def writeStyle(self, style):
        txt = []
        txt.extend(self.renderInline(style))
        log.warning("unknown tag node", repr(style))
        return txt

    def _generate_article_id_and_check_internal_link(self, obj):
        article = obj.get_parent_nodes_by_class(advtree.Article)
        wikiurl = ""
        internallink = False
        if article:
            wikiurl = getattr(article[0], "wikiurl", "")
        article_id = self.buildArticleID(wikiurl, obj.full_target)
        if article_id in self.articleids:
            internallink = True
        return article_id, internallink

    def _format_hyperlink_text_based_on_link_type(
        self, internallink, obj, href, text, article_id
    ):
        if not internallink:
            if not obj.target.startswith("#"):  # intrapage links are filtered
                text = f'<link href="{xmlescape(href)}">{text}</link>'
        else:
            text = f'<link href="#{article_id}">{text}</link>'
        return text

    def writeLink(self, obj):
        """Link nodes are intra wiki links"""
        href = obj.url

        # looking for internal links
        internallink = False
        article_id = None
        if isinstance(obj, advtree.ArticleLink) and obj.url:
            (
                article_id,
                internallink,
            ) = self._generate_article_id_and_check_internal_link(obj)

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
            text = "".join(txt)
            if not href:
                return [text]
        else:
            txt = urllib.parse.unquote(obj.target.encode("utf-8"))
            text = self.formatter.style_text(txt)

        text = self._format_hyperlink_text_based_on_link_type(
            internallink, obj, href, text, article_id
        )

        return [text]

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
            self.table_nesting
            and len(href) > pdfstyles.URL_REF_LEN
            and pdfstyles.URL_REF_IN_TABLE
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
                i.children = [URL(href)]
                self.references.append(i)
                self.url_map[href] = len(self.references)
        else:  # we are writing a reference section. we therefore directly print URLs
            txt = self.renderInline(obj)
            if any(href.startswith(url) for url in pdfstyles.URL_BLACKLIST):
                return ["".join(txt)]
            txt.append(
                ' <link href="{}">({})</link>'.format(
                    xmlescape(href), self.renderURL(urllib.parse.unquote(href))
                )
            )
            return ["".join(txt)]

        if not obj.children:
            linktext = f'<link href="{xmlescape(href)}">[{self.url_map[href]}]</link>'
        else:
            linktext = self.renderInline(obj)
            linktext.append(
                ' <super><link href="{}"><font size="10">[{}]</font></link></super> '.format(
                    xmlescape(href), self.url_map[href]
                )
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
        cmd = [
            "convert",
            img_path,
            "-flatten",
            "-coalesce",
            "-strip",
            img_path + ".png",
        ]
        try:
            process = subprocess.Popen(cmd, shell=False)
            _, status = os.waitpid(process.pid, 0)
            if status != 0:
                log.warning(
                    "img could not be converted. convert exited with non-zero return code:",
                    repr(cmd),
                )
                return ""
            return f"{img_path}.png"
        except OSError:
            log.warning("img could not be converted. cmd failed:", repr(cmd))
            return ""

    def getImgPath(self, target):
        if self.img_db:
            img_path = self.img_db.get_disk_path(
                target, size=800
            )  # FIXME: width should be obsolete now
            if img_path and img_path.lower().endswith("svg"):
                img_path = self.svg2png(img_path)
            if img_path:
                img_path = img_path.encode("utf-8")
                self.tmp_images.add(img_path)
            if not self.license_checker.display_image(target):
                if self.debug:
                    print(
                        "filtering image",
                        target,
                        self.license_checker.get_license_display_name(target),
                    )
                return None
        else:
            img_path = ""
        return img_path

    def _execute_image_conversion_commands(self, cmds, img_path):
        for cmd in cmds:
            try:
                ret = subprocess.call(cmd)
                if ret != 0:
                    log.warning(
                        f"converting broken image failed (return code: {ret}): {img_path}"
                    )
                    return ret
            except OSError:
                log.warning(f"converting broken image failed (OSError): {img_path}")
                raise

    def _fix_broken_images(self, _, img_path):
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
            # ticket 901, image:
            # http://en.wikipedia.org/wiki/File:WiMAXArchitecture.svg
            # correct preserving alpha:
            # convert broken.png white1000.png -compose Multiply
            # -composite +matte final.png
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

        self._execute_image_conversion_commands(cmds, img_path)
        try:
            del img
        except:
            log.warning("image can not be opened by PIL: %r" % img_path)
            raise
        self.fixed_images[img_path] = 0
        return 0

    def set_svg_default_size(self, img_node):
        image_info = self.img_db.imageinfo.get(img_node.full_target, {})
        if image_info.get("url", "").endswith(".svg"):
            width = image_info.get("width")
            height = image_info.get("height")
            if (
                width
                and height
                and img_node.width is None
                and img_node.height is None
                and img_node.is_inline()
            ):
                img_node.width = width
                img_node.height = height

    def _store_image_metadata(self, img_node, img_name):
        self.img_count += 1
        url = self.img_db.get_description_url(img_name) or self.img_db.get_url(img_name)
        url = (
            urllib.parse.unquote(url.encode("utf-8"))
            if url and pdfstyles.LINK_IMAGES
            else ""
        )
        if not self.test_mode:
            license_name = self.license_checker.get_license_display_name(img_name)
            contributors = self.img_db.get_contributors(img_node.target)
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

    def _calculate_image_dimensions(self, img_node):
        max_width = self.colwidth
        if self.table_nesting > 0 and not max_width:
            cell = img_node.get_parent_nodes_by_class(advtree.Cell)
            if cell:
                max_width = PRINT_WIDTH / len(cell[0].get_all_siblings()) - 10
        max_height = pdfstyles.IMG_MAX_THUMG_HEIGHT * PRINT_HEIGHT
        if self.table_nesting > 0:
            max_height = PRINT_HEIGHT / 4  # fixme this needs to be read from config
        if self.gallery_mode:
            max_height = PRINT_HEIGHT / 3  # same as above
        return max_width, max_height

    def _handle_invalid_image_url(self, img_node):
        if img_node.target is None:
            img_node.target = ""
        log.warning("invalid image url (obj.target: %r)" % img_node.target)
        return []

    def _determine_image_alignment(self, img_node):
        align = img_node.align
        if align in [None, "none"]:
            align = styleutils.get_text_alignment(img_node)
        if advtree.Center in [p.__class__ for p in img_node.get_parents()]:
            align = "center"
        return align

    def writeImageLink(self, img_node):
        if img_node.colon is True:
            items = []
            for node in img_node.children:
                items.extend(self.write(node))
            return items

        img_path = self.getImgPath(img_node.target)

        if not img_path:
            return self._handle_invalid_image_url(img_node)

        try:
            ret = self._fix_broken_images(img_node, img_path)
            if ret != 0:
                return []
        except:
            traceback.print_exc()
            log.warning("image skipped")
            return []

        max_width, max_height = self._calculate_image_dimensions(img_node)

        self.set_svg_default_size(img_node)

        width, height = self.image_utils.get_image_size(
            img_node, img_path, max_print_width=max_width, max_print_height=max_height
        )

        align = self._determine_image_alignment(img_node)
        txt = []
        if img_node.render_caption:
            txt = self.renderInline(img_node)

        is_inline = img_node.is_inline()

        if pdfstyles.LINK_IMAGES:
            url = self.img_db.get_description_url(
                img_node.target
            ) or self.img_db.get_url(img_node.target)
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
            self._store_image_metadata(img_node, img_name)

        if is_inline:
            txt = '{linkstart}<img src="{src}" width="{width:f}pt" height="{height:f}pt" valign="{align}"/>{linkend}'.format(
                src=str(img_path, "utf-8"),
                width=width,
                height=height,
                align="bottom",
                linkstart=linkstart,
                linkend=linkend,
            )
            return [txt]
        caption_txt = "".join(txt)
        figure = Figure(
            img_path,
            captionTxt=caption_txt,
            captionStyle=text_style("figure", in_table=self.table_nesting),
            imgWidth=width,
            imgHeight=height,
            margin=(0.2 * cm, 0.2 * cm, 0.2 * cm, 0.2 * cm),
            padding=(0.2 * cm, 0.2 * cm, 0.2 * cm, 0.2 * cm),
            borderColor=pdfstyles.IMG_BORDER_COLOR,
            align=align,
            url=url,
        )
        figure.float_figure = img_node.align not in ["center", "none"]
        return [figure]

    def _calculate_min_height_and_aspect_ratios(self, row, aspect_ratios, row_heights):
        min_height = 999999
        for cell in row:
            if cell:
                figure = cell[0]
                min_height = min(min_height, figure.imgHeight)
                aspect_ratios.append(figure.imgHeight / figure.imgWidth)
        row_heights.append(min_height)

    def _adjust_figure_dimensions_based_on_row_height(
        self, row, row_heights, row_idx, aspect_ratios
    ):
        for cell in row:
            if cell:
                figure = cell[0]
                figure.i.drawWidth = row_heights[row_idx] / aspect_ratios.pop(0)
                figure.i.drawHeight = row_heights[row_idx]

    def _add_caption_to_table(self, caption, table):
        txt = self.formatter.style_text(caption)
        elements = build_paragraph(txt, heading_style(mode="tablecaption"))
        elements.append(table)
        return elements

    def _process_node_and_add_to_row(self, node, row, perrow, data):
        if isinstance(node, advtree.ImageLink):
            node.align = "center"  # this is a hack. otherwise writeImage thinks this is an inline image
            res = self.write(node)
        else:
            res = self.write(node)
            try:
                res = build_paragraph(res)
            except:
                res = Paragraph("", text_style(in_table=self.table_nesting))
        if len(row) < perrow:
            row.append(res)
        else:
            data.append(row)
            row = []
            row.append(res)
        return row

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
            self.colwidth = PRINT_WIDTH / perrow - 12
        colwidths = [self.colwidth + 12] * perrow

        for node in obj.children:
            row = self._process_node_and_add_to_row(node, row, perrow, data)
        if len(row):
            while len(row) < perrow:
                row.append("")
            data.append(row)

        row_heights = []
        aspect_ratios = []
        for row in data:
            self._calculate_min_height_and_aspect_ratios(
                row, aspect_ratios, row_heights
            )

        for row_idx, row in enumerate(data):
            self._adjust_figure_dimensions_based_on_row_height(
                row, row_heights, row_idx, aspect_ratios
            )

        table = Table(data, colWidths=colwidths)
        table.setStyle([("VALIGN", (0, 0), (-1, -1), "TOP")])
        self.gallery_mode = False
        caption = obj.attributes.get("caption", None)
        self.colwidth = None
        if caption:
            return self._add_caption_to_table(caption, table)
        return [table]

    def _len(self, txt):
        in_tag = False
        length = 0
        for char in txt:
            if char == "<":
                in_tag = True
            elif char == ">":
                in_tag = False
            elif not in_tag:
                length += 1
        return length

    def _parse_html_character(self, character, words, in_space, in_tag, word):
        if character == "<":
            in_tag = True
        if character in [" ", "\t"]:
            if not in_tag and not in_space:
                words.append("".join(word))
                word = []
            word.append(character)
            in_space = True
        else:
            if in_space and not in_tag:
                words.append("".join(word))
                word = []
            word.append(character)
            in_space = False
        if character == ">":
            in_tag = False
        return in_space, in_tag, word

    def _get_frags(self, txt):
        words = []
        word = []
        in_tag = False
        in_space = False
        for character in txt:
            in_space, in_tag, word = self._parse_html_character(
                character, words, in_space, in_tag, word
            )
        if word:
            words.append("".join(word))
        return words

    def breakLongLines(self, txt, char_limit):
        broken_source = []
        for line in txt.split("\n"):
            if len(line) < char_limit:
                broken_source.append(line)
            else:
                words = self._get_frags(line)
                while words:
                    new_line = [words.pop(0)]
                    while (
                        words
                        and (self._len("".join(new_line)) + self._len(words[0]))
                        < char_limit
                    ):
                        new_line.append(words.pop(0))
                    broken_source.append("".join(new_line))
        return "\n".join(broken_source)

    def _write_source_in_source_mode(self, node, src_lang, lexer, font_size):
        source_formatter = ReportlabFormatter(
            font_size=font_size,
            font_name="FreeMono",
            background_color="#eeeeee",
            line_numbers=False,
        )
        source_formatter.encoding = "utf-8"
        self.formatter.source_mode += 1

        source = "".join(self.renderInline(node))
        self.formatter.source_mode -= 1
        source = source.replace("\t", " " * pdfstyles.TABSIZE)
        max_char_on_line = max([len(line) for line in source.split("\n")])
        char_limit = max(
            1, int(pdfstyles.SOURCE_MAX_LINE_LEN / (max(1, self.current_col_count)))
        )

        if max_char_on_line > char_limit:
            source = self.breakLongLines(source, char_limit)
        txt = ""
        try:
            txt = str(highlight(source, lexer, source_formatter), "utf-8")
            self.font_switcher.register_default_font(pdfstyles.DEFAULT_LATIN_FONT)
            txt = self.font_switcher.fontify_text(txt)
            self.font_switcher.register_default_font(pdfstyles.DEFAULT_FONT)
            if node.vlist.get("enclose", False) == "none":
                txt = re.sub("<para.*?>", "", txt).replace("</para>", "")
                return txt
            return XPreformatted(
                txt, text_style(mode="source", in_table=self.table_nesting)
            )
        except:
            traceback.print_exc()
            log.error(
                f"unsuitable lexer for source code language: {src_lang} - Lexer: {lexer.__class__.__name__}"
            )
            return None

    def writeSource(self, node):
        lang_map = {
            "lisp": lexers.CommonLispLexer()
        }  # custom Mapping between mw-markup source attrs to pygement lexers if get_lexer_by_name fails

        def get_lexer(name):
            try:
                return lexers.get_lexer_by_name(name)
            except lexers.ClassNotFound:
                lexer = lang_map.get(name)
                if lexer:
                    return lexer
                traceback.print_exc()
                log.error("unknown source code language: %s" % repr(name))
                return None

        src_lang = node.vlist.get("lang", "").lower()
        lexer = get_lexer(src_lang)
        if lexer:
            rtl, self.rtl = self.rtl, False
            width = None
            avail_width = self.getAvailWidth()
            font_size = pdfstyles.FONT_SIZE
            while not width or width > avail_width:
                res = self._write_source_in_source_mode(
                    node, src_lang, lexer, font_size
                )
                if res.__class__ != XPreformatted:
                    break
                width, _ = res.wrap(avail_width, pdfstyles.PAGE_HEIGHT)
                font_size -= 0.5
            self.rtl = rtl
            if res:
                return [res]
        return self.writePreFormatted(node)

    def writeTeletyped(self, node):
        return self.renderInline(node)

    writeCode = writeTeletyped
    writeVar = writeTeletyped

    def writeBreakingReturn(self, _):
        return ["<br />"]

    def writeHorizontalRule(self, _):
        return [
            HRFlowable(
                width="100%",
                spaceBefore=3,
                spaceAfter=6,
                color=colors.black,
                thickness=0.25,
            )
        ]

    def writeIndex(self, node):
        log.warning("unhandled Index Node - rendering child nodes")
        return self.renderChildren(node)  # fixme: handle index nodes properly

    def writeReference(self, node, is_link=False):
        ref_name = node.attributes.get("name")
        if not getattr(node, "ref_num", None):
            if ref_name and not node.children:
                ref_num = self.ref_name_map.get(ref_name, "")
            else:
                i = parser.Item()
                for child in node.children:
                    i.append_child(child)
                self.references.append(i)
                ref_num = len(self.references)
                self.ref_name_map[ref_name] = ref_num
            node.ref_num = ref_num
        if getattr(node, "no_display", False):
            return []
        if is_link:
            return ["[%s]" % len(self.references)]
        else:
            return ['<super><font size="10">[%s]</font></super>' % node.ref_num]

    def writeReferenceList(self, _=None):
        if self.references:
            self.ref_mode = True
            ref_list = self.writeItemList(self.references, style="referencelist")
            self.references = []
            self.ref_mode = False
            self.reference_list_rendered = True
            return ref_list
        else:
            self.reference_list_rendered = True
            return []

    def writeCenter(self, node):
        return self.renderMixed(
            node, text_style(mode="center", in_table=self.table_nesting)
        )

    def writeDiv(self, node):
        if not node.children:
            div_height = node.style.get("height")
            if div_height:
                height = min(styleutils.scale_length(div_height), PRINT_HEIGHT - 20)
                if height:
                    return [Spacer(0, height)]
            return []
        if (
            getattr(node, "border", False)
            and not node.get_parent_nodes_by_class(Table)
            and not node.get_child_nodes_by_class(advtree.PreFormatted)
        ):
            return self.renderMixed(
                node,
                text_style(
                    mode="box",
                    indent_lvl=self.para_indent_level,
                    in_table=self.table_nesting,
                ),
            )
        else:
            return self.renderMixed(
                node,
                text_style(
                    indent_lvl=self.para_indent_level, in_table=self.table_nesting
                ),
            )

    def writeSpan(self, span_node):
        return self.renderInline(span_node)

    def writeFont(self, font_node):  # FIXME we should evaluate the info in the fonttag
        return self.renderInline(font_node)

    def writeStrike(self, strike_node):
        return self.renderInline(strike_node)

    writeS = writeStrike
    writeDeleted = writeStrike

    def writeImageMap(self, node):
        if node.imagemap.imagelink:
            return self.write(node.imagemap.imagelink)
        else:
            return []

    def writeTagNode(self, tag):
        if getattr(tag, "caption", None) in ["hiero"]:
            return []
        return self.renderChildren(tag)  # FIXME

    def writeItem(self, item, style="itemize", counter_id=None, reset_counter=False):
        items = []
        seq_reset = (
            '<seqreset id="liCounter%d" base="0" />' % counter_id
            if reset_counter
            else ""
        )

        if style == "itemize":
            item_prefix = "<bullet>%s</bullet>" % pdfstyles.LIST_ITEM_STYLE
        elif style == "referencelist":
            item_prefix = '<bullet>%s[<seq id="liCounter%d" />]</bullet>' % (
                seq_reset,
                counter_id,
            )
        elif style == "enumerate":
            item_prefix = '<bullet>%s<seq id="liCounter%d" />.</bullet>' % (
                seq_reset,
                counter_id,
            )
        elif style.startswith("enumerateLetter"):
            item_prefix = (
                '<bullet>%s<seqformat id="liCounter%d" value="%s"/><seq id="liCounter%d" />.</bullet>'
                % (seq_reset, counter_id, style[-1], counter_id)
            )
        else:
            log.warn("invalid list style:", repr(style))
            item_prefix = ""

        list_indent = max(0, (self.list_indentation + self.para_indent_level))
        if self.license_mode:
            para_style = text_style(mode="licenselist", indent_lvl=list_indent)
        elif self.ref_mode:
            para_style = text_style(mode="references", indent_lvl=list_indent)
        else:
            para_style = text_style(
                mode="list", indent_lvl=list_indent, in_table=self.table_nesting
            )
        if reset_counter:  # first list item gets extra spaceBefore
            para_style.spaceBefore = text_style().spaceBefore

        leaf = item.get_first_leaf()  # strip leading spaces from list items
        if leaf and hasattr(leaf, "caption"):
            leaf.caption = leaf.caption.lstrip()
        items = self.renderMixed(item, para_style=para_style, text_prefix=item_prefix)

        return items

    def _determine_list_style(self, numbered, lst):
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
        return style

    def writeItemList(self, lst, numbered=False, style="itemize"):
        self.list_indentation += 1
        items = []
        if style != "referencelist":
            style = self._determine_list_style(numbered, lst)

        self.list_counter_id += 1
        counter_id = self.list_counter_id
        for i, node in enumerate(lst):
            if isinstance(node, parser.Item):
                reset_counter = (
                    i == 0
                )  # we have to manually reset sequence counters. due to w/h calcs with wrap reportlab gets confused
                item = self.writeItem(
                    node,
                    style=style,
                    counter_id=counter_id,
                    reset_counter=reset_counter,
                )
                items.extend(item)
            else:
                log.warning(f"got {node.__class__.__name__} node in itemlist - skipped")
        self.list_indentation -= 1
        return items

    def getAvailWidth(self):
        if self.table_nesting > 1 and self.colwidth:
            availwidth = self.colwidth - 2 * pdfstyles.CELL_PADDING
        else:
            availwidth = (
                pdfstyles.PRINT_WIDTH
                - self.para_indent_level * pdfstyles.PARA_LEFT_INDENT
            )
        return availwidth

    def writeCaption(self, node):
        txt = []
        for child in node.children:
            res = self.write(child)
            if is_inline(res):
                txt.extend(res)
        txt.insert(0, "<b>")
        txt.append("</b>")
        return build_paragraph(txt, heading_style(mode="tablecaption"))

    def renderCaption(self, table):
        res = []
        for row in table.children[:]:
            if row.__class__ == Caption:
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

    def _extra_cell_padding(self, cell):
        return (
            cell.get_child_nodes_by_class(NamedURL)
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
        if self._extra_cell_padding(cell):
            elements.append(Spacer(0, 1))
        if getattr(cell, "is_header", False):
            self.formatter.strong_style += 1
            for child in cell.children:
                child.is_header = True
        elements.extend(
            self.renderMixed(
                cell, text_style(in_table=self.table_nesting, text_align=align)
            )
        )

        for i, element in enumerate(elements):
            if isinstance(element, str):
                elements[i] = build_paragraph([element])[0]

        if getattr(cell, "is_header", False):
            self.formatter.strong_style -= 1

        return elements

    def writeRow(self, row):
        new_row = []
        for cell in row:
            if cell.__class__ == advtree.Cell:
                new_row.append(self.writeCell(cell))
            else:
                log.warning(
                    "table row contains non-cell node, skipped: %r"
                    % cell.__class__.__name__
                )
        return new_row

    def _correct_width(self, element):
        width_correction = 0
        if hasattr(element, "style"):
            width_correction += element.style.leftIndent + element.style.rightIndent
        return width_correction

    def getMinElementSize(self, element):
        try:
            w_min, h_min = element.wrap(0, pdfstyles.PAGE_HEIGHT)
        except TypeError:  # issue with certain cjk text
            return 0, 0
        min_width = w_min + self._correct_width(element)
        min_width += 2 * pdfstyles.CELL_PADDING
        return min_width, h_min

    def getMaxParaWidth(self, paragraph, print_width):
        kind = paragraph.blPara.kind
        space_width = stringWidth(
            " ", paragraph.style.fontName, paragraph.style.fontSize
        )
        total_width = 0
        current_width = 0
        for line in paragraph.blPara.lines:
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
            element.wrap(PRINT_WIDTH, PRINT_HEIGHT)
            pad = 2 * pdfstyles.CELL_PADDING
            width = self.getMaxParaWidth(element, PRINT_WIDTH)
            return width + pad, 0
        _, h_max = element.wrap(10 * pdfstyles.PAGE_WIDTH, pdfstyles.PAGE_HEIGHT)
        rows = h_min / h_max if h_max > 0 else 1
        max_width = rows * w_min
        max_width += 2 * rows * pdfstyles.CELL_PADDING
        return max_width, h_max

    def getCurrentColWidth(self, table, cell, col_idx):
        colwidth = sum(table.colwidths[col_idx : col_idx + cell.colspan])
        return colwidth

    def getCellSize(self, elements, _):
        min_width = 0
        max_width = 0
        for element in elements:
            if element.__class__ == DummyTable:
                pad = 2 * pdfstyles.CELL_PADDING
                return sum(element.min_widths) + pad, sum(element.max_widths) + pad
            w_min, h_min = self.getMinElementSize(element)
            min_width = max(min_width, w_min)
            w_max, _ = self.getMaxElementSize(element, w_min, h_min)
            max_width = max(max_width, w_max)

        return min_width, max_width

    def _calculate_and_update_cell_widths(self, row, min_widths, max_widths):
        for col_idx, cell in enumerate(row.children):
            content = self.renderCell(cell)
            min_width, max_width = self.getCellSize(content, cell)
            cell.min_width, cell.max_width = min_width, max_width
            if cell.colspan == 1:
                min_widths[col_idx] = max(min_width, min_widths[col_idx])
                max_widths[col_idx] = max(max_width, max_widths[col_idx])
            cell.col_idx = col_idx

    def _adjust_colspan_cell_widths(self, cell, min_widths, max_widths, col_idx):
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

    def _get_table_size(self, table):
        min_widths = [0 for _ in range(table.num_cols)]
        max_widths = [0 for _ in range(table.num_cols)]
        for row in table.children:
            self._calculate_and_update_cell_widths(row, min_widths, max_widths)

        for row in table.children:  # handle colspanned cells
            col_idx = 0
            for cell in row.children:
                if cell.colspan > 1:
                    self._adjust_colspan_cell_widths(
                        cell, min_widths, max_widths, col_idx
                    )
                col_idx += 1
        return min_widths, max_widths

    def getTableSize(self, table):
        table.min_widths, table.max_widths = self._get_table_size(table)
        table_width = sum(table.min_widths)
        if (table_width > self.getAvailWidth() and self.table_nesting > 1) or (
            table_width
            > (
                pdfstyles.PAGE_WIDTH
                - (pdfstyles.PAGE_MARGIN_LEFT + pdfstyles.PAGE_MARGIN_RIGHT) / 4
            )
            and self.table_nesting == 1
        ):
            pdfstyles.CELL_PADDING = 2
            total_padding = table.num_cols * pdfstyles.CELL_PADDING
            scale = (pdfstyles.PRINT_WIDTH - total_padding) / (
                sum(table.min_widths) - total_padding
            )
            log.info(f"scaling down text in wide table by factor of {scale:2f}")
            table.rel_font_size = self.formatter.rel_font_size
            self.formatter.set_relative_font_size(scale)
            table.small_table = True
            table.min_widths, table.max_widths = self._get_table_size(table)

    def emptyTable(self, table):
        for row in table.children:
            if row.__class__ == advtree.Row:
                for _ in row.children:
                    return False
        return True

    def writeTable(self, table):
        if self.emptyTable(table):
            return []
        self.table_nesting += 1
        elements = []
        if (
            len(table.children) >= pdfstyles.MIN_ROWS_FOR_BREAK
            and self.table_nesting == 1
        ):
            elements.append(CondPageBreak(pdfstyles.MIN_TABLE_SPACE))
        elements.extend(self.renderCaption(table))
        rltables.flip_dir(table, rtl=self.rtl)
        rltables.check_spans(table)
        table.num_cols = table.numcols
        self.table_size_calc += 1
        if not getattr(table, "min_widths", None) and not getattr(
            table, "max_widths", None
        ):
            self.getTableSize(table)
        self.table_size_calc -= 1
        if self.table_size_calc > 0:
            self.table_nesting -= 1
            return [DummyTable(table.min_widths, table.max_widths)]
        avail_width = self.getAvailWidth()
        stretch = (
            self.table_nesting == 1 and table.attributes.get("width", "") == "100%"
        )
        table.colwidths = rltables.optimize_widths(
            table.min_widths,
            table.max_widths,
            avail_width,
            stretch=stretch,
            table=table,
        )
        table_data = []
        for row in table.children:
            row_data = []
            for col_idx, cell in enumerate(row.children):
                self.colwidth = self.getCurrentColWidth(table, cell, col_idx)
                row_data.append(self.write(cell))
            table_data.append(row_data)
        pdf_table = Table(table_data, colWidths=table.colwidths, splitByRow=1)
        pdf_table.setStyle(rltables.get_styles(table))
        pdf_table.hAlign = pdfstyles.TABLE_ALIGN
        if TABLE_STYLE.get("spaceBefore", 0) > 0:
            elements.append(Spacer(0, TABLE_STYLE["spaceBefore"]))
        elements.append(pdf_table)
        if TABLE_STYLE.get("spaceAfter", 0) > 0:
            elements.append(Spacer(0, TABLE_STYLE["spaceAfter"]))
        self.table_nesting -= 1
        if self.table_nesting == 0:
            self.colwidth = 0
        if getattr(table, "small_table", False):
            pdfstyles.CELL_PADDING = 3
            self.formatter.set_relative_font_size(table.rel_font_size)
        return elements

    def addAnchors(self, table):
        anchors = ""
        for article_id in self.articleids:
            new_anchor = f'<a name="{article_id}" />'
            anchors = f"{anchors}{new_anchor}"
        paragraph = Paragraph(anchors, text_style())

        cell = table._cellvalues[0][0]
        if not cell:
            cell = [paragraph]
        else:
            cell.append(paragraph)

    def delAnchors(self, table):
        cells = table._cellvalues[0][0]
        if cells:
            cells.pop()

    def has_cache(self):
        return self.math_cache_dir and os.path.isdir(self.math_cache_dir)

    def _get_cached_math_image_path(self, source, density, imgpath):
        _md5 = md5()
        _md5.update(source.encode("utf-8"))
        math_id = _md5.hexdigest()
        cached_path = os.path.join(
            self.math_cache_dir,
            f"{math_id[0]}/{math_id[1]}/{math_id}-{density}.png",
        )
        if os.path.exists(cached_path):
            imgpath = cached_path
        return imgpath, cached_path

    def _move_image_to_cache(self, imgpath, cached_path):
        if not os.path.isdir(os.path.dirname(cached_path)):
            os.makedirs(os.path.dirname(cached_path))
        shutil.move(imgpath, cached_path)
        imgpath = cached_path
        return imgpath

    def writeMath(self, node):
        source = re.compile("\n+").sub(
            "\n", node.caption.strip()
        )  # remove multiple newlines, as this could break the mathRenderer
        if not source:
            return []
        if source.endswith("\\"):
            source += " "

        try:
            density = int(os.environ.get("MATH_RESOLUTION", "120"))
        except ValueError:
            density = (
                120  # resolution in dpi in which math images are rendered by texvc
            )

        imgpath = None

        if self.has_cache():
            imgpath, cached_path = self._get_cached_math_image_path(
                source, density, imgpath
            )

        if not imgpath:
            imgpath = render_math(
                source,
                output_path=self.tmpdir,
                output_mode="png",
                render_engine="texvc",
                resolution_in_dpi=density,
            )
            if not imgpath:
                return []
            if self.has_cache():
                imgpath = self._move_image_to_cache(imgpath, cached_path)

        img = PilImage.open(imgpath)
        if self.debug:
            log.info("math png at:", imgpath)
        width, height = img.size
        del img

        if width > pdfstyles.max_math_width or height > pdfstyles.MAX_MATH_HEIGHT:
            log.info(
                f"skipping math formula, png to big: {source}, w:{width}, h:{height}"
            )
            return ""
        if self.table_nesting:  # scale down math-formulas in tables
            width = width * pdfstyles.SMALL_FONT_SIZE / pdfstyles.FONT_SIZE
            height = height * pdfstyles.SMALL_FONT_SIZE / pdfstyles.FONT_SIZE

        scale = (self.getAvailWidth()) / (width / density * 72)
        if scale < 1:
            width *= scale
            height *= scale

        # the vertical image placement is calculated below:
        # the "normal" height of a single-line formula is 17px
        img_align_value = -(height - 15) / (2 * density)
        img_align = f"{img_align_value}in"
        # the non-breaking-space is needed to
        # force whitespace after the formula
        return [
            f'<img src="{imgpath.encode(sys.getfilesystemencoding())}" width="{width / density * 72:f}pt" height="{height / density * 72:f}pt" valign="{img_align}" />'
        ]

    def writeTimeline(self, node):
        img_path = timeline.draw_timeline(node.timeline, self.img_db.nuwiki.path)
        if img_path:
            # width and height should be parsed by the....parser
            # and not guessed by the writer
            node.width = PRINT_WIDTH
            node.is_inline = lambda: False
            width, height = self.image_utils.get_image_size(
                node,
                img_path,
            )
            return [
                Figure(img_path, "", text_style(), img_width=width, img_height=height)
            ]
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
    rl_writer = RlWriter(
        env, strict=strict, debug=debug, mathcache=mathcache, lang=lang
    )
    if coverimage is None and env.configparser.has_section("pdf"):
        coverimage = env.configparser.get("pdf", "coverimage", None)

    if profile:
        cProfile.runctx(
            "r.writeBook(output=output, coverimage=coverimage, status_callback=status_callback)",
            globals(),
            locals(),
            os.path.expanduser(profile),
        )
    else:
        rl_writer.writeBook(
            output=output, coverimage=coverimage, status_callback=status_callback
        )


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
