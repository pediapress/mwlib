#! /usr/bin/env py.test
# -*- coding: utf-8 -*-

import os
import shutil
import tempfile

from mwlib.mathutils import renderMath
from mwlib.xfail import xfail


class TestMathUtils(object):
    def setup_method(self, method):
        self.tmpdir = tempfile.mkdtemp()

    def teardown_method(self, method):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def blahtexml_present(self):
        ret = os.system('blahtexml')
        print "BLAHTEX:", ret
        if ret != 0:
            return False
        else:
            return True

    def texvc_present(self):
        ret = os.system('texvc')
        if ret != 0:
            return False
        else:
            return True

    def test_math(self):
        latexlist = [r"\sqrt{4}=2",
                     r"a^2 + b^2 = c^2\,",
                     r"E = m c^2",
                     r"\begin{matrix}e^{\mathrm{i}\,\pi}\end{matrix}+1=0\;",
                     r"1\,\mathrm{\frac{km}{h}} = 0{,}2\overline{7}\,\mathrm{\frac{m}{s}}",
                     r'\text{björn}',
                     ]
        for latex in latexlist:
            latex = unicode(latex, 'utf-8')
            if self.blahtexml_present():
                res = renderMath(latex, self.tmpdir, output_mode='png', render_engine='blahtexml')
                assert res
                res = renderMath(latex, self.tmpdir, output_mode='mathml', render_engine='blahtexml')
                assert res
            if self.texvc_present():
                res = renderMath(latex, self.tmpdir, output_mode='png', render_engine='texvc')
                assert res

    @xfail
    def test_math_complex(self):

        latex = r"""\begin{array}{ccc}
    F^2\sim W&\Leftrightarrow&\frac{F_1^2}{F_2^2}=\frac{W_1}{W_2}\\
    \ln\frac{F_1}{F_2}\,\mathrm{Np}&=&
    \frac{1}{2}\ln\frac{W_1}{W_2}\,\mathrm{Np}\\
    20\,\lg\frac{F_1}{F_2}\,\mathrm{dB}&=&
    10\,\lg\frac{W_1}{W_2}\,\mathrm{dB}
    \end{array}"""
        latex = unicode(latex)
        if self.blahtexml_present():
            res = renderMath(latex, self.tmpdir, output_mode='mathml', render_engine='blahtexml')
            assert res
        else:
            assert False

    def test_single_quote_bug(self):
        """http://code.pediapress.com/wiki/ticket/241"""

        if self.texvc_present():
            res = renderMath(u"f'(x) = x", self.tmpdir, output_mode='png', render_engine='texvc')
            assert res
