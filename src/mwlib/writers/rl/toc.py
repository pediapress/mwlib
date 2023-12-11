#! /usr/bin/env python

# Copyright (c) 2007, 2008, 2009 PediaPress GmbH
# See README.txt for additional licensing information.

import os
import shutil
import subprocess

from reportlab.platypus.doctemplate import SimpleDocTemplate
from reportlab.platypus.paragraph import Paragraph
from reportlab.platypus.tables import Table

from mwlib.writers.rl import fontconfig, pdfstyles


class TocRenderer:
    def __init__(self):
        font_switcher = fontconfig.RLFontSwitcher()
        font_switcher.font_paths = fontconfig.font_paths
        font_switcher.register_default_font(pdfstyles.DEFAULT_FONT)
        font_switcher.register_font_def_list(fontconfig.fonts)
        font_switcher.register_reportlab_fonts(fontconfig.fonts)

    def build(self, pdfpath, toc_entries, has_title_page=False, rtl=False):
        outpath = os.path.dirname(pdfpath)
        tocpath = os.path.join(outpath, "toc.pdf")
        finalpath = os.path.join(outpath, "final.pdf")
        self.render_toc(tocpath, toc_entries, rtl=rtl)
        return self.comine_pdfs(pdfpath, tocpath, finalpath, has_title_page)

    def _get_col_widths(self):
        paragraph = Paragraph(
            "<b>%d</b>" % 9999, pdfstyles.text_style(mode="toc_article",
                                                     text_align="right")
        )
        width, _ = paragraph.wrap(0, pdfstyles.PRINT_HEIGHT)
        # subtracting 30pt below is *probably* necessary b/c
        # of the table margins
        return [pdfstyles.PRINT_WIDTH - width - 30, width]

    def render_toc(self, tocpath, toc_entries, rtl):
        doc = SimpleDocTemplate(tocpath, pagesize=(pdfstyles.PAGE_WIDTH,
                                                   pdfstyles.PAGE_HEIGHT))
        elements = []
        elements.append(
            Paragraph(
                _("Contents"),
                pdfstyles.heading_style(
                    mode="Chapter",
                    text_align="left" if not rtl else "right"),
            )
        )
        toc_table = []
        styles = []
        col_widths = self._get_col_widths()
        for row_idx, (lvl, txt, page_num) in enumerate(toc_entries):
            if lvl == "article":
                page_num = str(page_num)
            elif lvl == "Chapter":
                page_num = "<b>%d</b>" % page_num
                styles.append(("TOPPADDING", (0, row_idx), (-1, row_idx), 10))
            elif lvl == "group":
                page_num = " "
                styles.append(("TOPPADDING", (0, row_idx), (-1, row_idx), 10))

            toc_table.append(
                [
                    Paragraph(
                        txt, pdfstyles.text_style(mode="toc_%s" % str(lvl),
                                                  text_align="left")
                    ),
                    Paragraph(
                        page_num, pdfstyles.text_style(mode="toc_article",
                                                       text_align="right")
                    ),
                ]
            )
        table = Table(toc_table, colWidths=col_widths)
        table.setStyle(styles)
        elements.append(table)
        doc.build(elements)

    def run_cmd(self, cmd):
        try:
            retcode = subprocess.call(cmd, stdout=subprocess.PIPE)
        except OSError:
            retcode = 1
        return retcode

    def pdftk(self, pdfpath, tocpath, finalpath, has_title_page):
        cmd = [
            "pdftk",
            "A=%s" % pdfpath,
            "B=%s" % tocpath,
        ]
        if not has_title_page:
            cmd.extend(["cat", "B", "A"])
        else:
            cmd.extend(["cat", "A1", "B", "A2-end"])
        cmd.extend(["output", finalpath])
        return self.run_cmd(cmd)

    def pdfsam(self, pdfpath, tocpath, finalpath, has_title_page):
        cmd = ["pdfsam-console"]
        if not has_title_page:
            cmd.extend(["-f", tocpath, "-f", pdfpath])
        else:
            cmd.extend(["-f", pdfpath, "-f", tocpath,
                        "-f", pdfpath, "-u", "1-1:all:2-:"])
        cmd.extend(["-o", finalpath, "-overwrite", "concat"])
        return self.run_cmd(cmd)

    def comine_pdfs(self, pdfpath, tocpath, finalpath, has_title_page):
        if os.path.splitext(pdfpath)[1] == ".pdf":
            safe_pdfpath = pdfpath
        else:
            safe_pdfpath = pdfpath + ".pdf"
            shutil.move(pdfpath, safe_pdfpath)
        retcode = self.pdfsam(safe_pdfpath, tocpath,
                              finalpath, has_title_page=has_title_page)
        if retcode != 0:
            retcode = self.pdftk(safe_pdfpath, tocpath, finalpath,
                                 has_title_page=has_title_page)
        if retcode == 0:
            shutil.move(finalpath, pdfpath)
        if os.path.exists(tocpath):
            os.unlink(tocpath)
        return retcode
