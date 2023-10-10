#!/usr/bin/env pytest

import os
import shutil
import tempfile

import pytest
from mwlib.mw_math.mathutils import render_math


@pytest.fixture
def tmpdir():
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


def blahtexml_present():
    ret = os.system("blahtexml")
    return ret == 0


def texvc_present():
    ret = os.system("texvc")
    return ret == 0


@pytest.mark.xfail
def test_math(tmpdir):
    latexlist = [
        r"\sqrt{4}=2",
        r"a^2 + b^2 = c^2\,",
        r"E = m c^2",
        r"\begin{matrix}e^{\mathrm{i}\,\pi}\end{matrix}+1=0\;",
        r"1\,\mathrm{\frac{km}{h}} = 0{,}2\overline{7}\,\mathrm{\frac{m}{s}}",
        r"\text{björn}",
    ]
    for latex in latexlist:
        if blahtexml_present():
            res = render_math(latex, tmpdir, output_mode="png", render_engine="blahtexml")
            assert res
            res = render_math(latex, tmpdir, output_mode="mathml", render_engine="blahtexml")
            assert res


@pytest.mark.xfail
def test_math_complex(tmpdir):
    latex = r"""\begin{array}{ccc}
F^2\sim W&\Leftrightarrow&\frac{F_1^2}{F_2^2}=\frac{W_1}{W_2}\\
\ln\frac{F_1}{F_2}\,\mathrm{Np}&=&
\frac{1}{2}\ln\frac{W_1}{W_2}\,\mathrm{Np}\\
20\,\lg\frac{F_1}{F_2}\,\mathrm{dB}&=&
10\,\lg\frac{W_1}{W_2}\,\mathrm{dB}
\end{array}"""
    latex = str(latex)
    if blahtexml_present():
        res = render_math(latex, tmpdir, output_mode="mathml", render_engine="blahtexml")
        assert res
    else:
        assert False


def test_single_quote_bug(tmpdir):
    """https://code.pediapress.com/wiki/ticket/241"""

    if texvc_present():
        res = render_math("f'(x) = x", tmpdir, output_mode="png", render_engine="texvc")
        assert res
