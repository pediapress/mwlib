from mwlib.writerbase import renderMath
from mwlib.xfail import xfail 

def test_math():
    latexlist = [r"\sqrt{4}=2",
                 r"a^2 + b^2 = c^2\,",
                 r"E = m c^2",
                 r"\begin{matrix}e^{\mathrm{i}\,\pi}\end{matrix}+1=0\;",
                 r"1\,\mathrm{\frac{km}{h}} = 0{,}2\overline{7}\,\mathrm{\frac{m}{s}}",
                 ]
    for latex in latexlist:
        res = renderMath(latex, '/tmp/math', output_mode='png', render_engine='blahtexml')
        assert res
        res = renderMath(latex, '/tmp/math', output_mode='mathml', render_engine='blahtexml')
        assert res
        res = renderMath(latex, '/tmp/math', output_mode='png', render_engine='texvc')
        assert res

@xfail 
def test_math_complex():

    latex = r"""\begin{array}{ccc}
F^2\sim W&\Leftrightarrow&\frac{F_1^2}{F_2^2}=\frac{W_1}{W_2}\\
\ln\frac{F_1}{F_2}\,\mathrm{Np}&=&
\frac{1}{2}\ln\frac{W_1}{W_2}\,\mathrm{Np}\\
20\,\lg\frac{F_1}{F_2}\,\mathrm{dB}&=&
10\,\lg\frac{W_1}{W_2}\,\mathrm{dB}
\end{array}"""

    res = renderMath(latex, '/tmp/math', output_mode='mathml', render_engine='blahtexml')
    assert res
