#! /usr/bin/env python

# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.

import os
import popen2
import tempfile
import shutil

try:
    import xml.etree.ElementTree as ET
except:
    from elementtree import ElementTree as ET

from mwlib import log

log = log.Log('mwlib.math_utils')

def _renderMathBlahtex(latex, output_path, output_mode):
    
    if output_mode == 'mathml':
        cmd = 'blahtexml --texvc-compatible-commands --mathml'
    elif output_mode == 'png':
        cmd = 'blahtexml --texvc-compatible-commands --png'
    else:
        return None
    curdir = os.path.abspath(os.curdir)
    os.chdir(output_path)
    latex = latex.strip()
    r, w, e = popen2.popen3(cmd)
    w.write(latex.encode('utf-8'))
    w.close()
    error = e.read()
    result = r.read()
    r.close()
    e.close()
    os.chdir(curdir)

    if result:
        p = ET.fromstring(result)
        if output_mode == 'png':
            r = p.getiterator('png')
            if r:
                png_fn =  r[0].findtext('md5')
                if png_fn:
                    png_fn = os.path.join(output_path, png_fn + '.png')
                    if os.path.exists(png_fn):
                        return png_fn
        elif output_mode == 'mathml':
            mathml = p.getiterator('mathml')
            if mathml:
                mathml = mathml[0]
                mathml.set("xmlns","http://www.w3.org/1998/Math/MathML")
                return mathml
    log.error('error converting math (blahtexml). source: %r \nerror: %r' % (latex, result))
    return None

def _renderMathTexvc(latex, output_path, output_mode='png'):
    """only render mode is png"""
    
    cmd = "texvc %s %s '%s' utf-8" % (output_path, output_path, latex.encode('utf-8'))
    r= os.popen(cmd)
    result = r.read()
    r.close()
    if output_mode == 'png':
        if len(result) >= 32:
            png_fn = os.path.join(output_path, result[1:33] + '.png')
            if os.path.exists(png_fn):
                return png_fn
            
    log.error('error converting math (texvc). source: %r \nerror: %r' % (latex, result))              
    return None
    
def renderMath(latex, output_path=None, output_mode='png', render_engine='blahtexml'):
    """
    @param latex: LaTeX code
    @type latex: unicode
    
    @param output_mode: one of the values 'png' or 'mathml'. mathml only works
        with blahtexml as render_engine
    @type output_mode: str
    
    @param render_engine: one of the value 'blahtexml' or 'texvc'
    @type render_engine: str

    @returns: either path to generated png or mathml string
    @rtype: basestring
    """
    
    assert isinstance(latex, unicode), 'latex must be of type unicode'
    
    if output_mode == 'png' and not output_path:
        log.error('math rendering with output_mode png requires an output_path')
        raise
    removeTmpDir = False
    if output_mode == 'mathml' and not output_path:
        output_path = tempfile.mkdtemp()
        removeTmpDir = True
    output_path = os.path.abspath(output_path)
    result = None
    if render_engine == 'blahtexml':
        result = _renderMathBlahtex(latex, output_path=output_path, output_mode=output_mode)
    if not result and output_mode == 'png':
        result = _renderMathTexvc(latex, output_path=output_path, output_mode=output_mode)

    if removeTmpDir:
        shutil.rmtree(output_path)

    return result


if __name__ == "__main__":

    latex = "\\sqrt{4}=2"

##     latexlist = ["\\sqrt{4}=2",
##                  r"a^2 + b^2 = c^2\,",
##                  r"E = m c^2",
##                  r"\begin{matrix}e^{\mathrm{i}\,\pi}\end{matrix}+1=0\;",
##                  r"1\,\mathrm{\frac{km}{h}} = 0{,}2\overline{7}\,\mathrm{\frac{m}{s}}",
##                  r"""\begin{array}{ccc}
## F^2\sim W&\Leftrightarrow&\frac{F_1^2}{F_2^2}=\frac{W_1}{W_2}\\
## \ln\frac{F_1}{F_2}\,\mathrm{Np}&=&
## \frac{1}{2}\ln\frac{W_1}{W_2}\,\mathrm{Np}\\
## 20\,\lg\frac{F_1}{F_2}\,\mathrm{dB}&=&
## 10\,\lg\frac{W_1}{W_2}\,\mathrm{dB}
## \end{array}
##                  """,
##         ]
    
    #print renderMath(latex, '/tmp/math', output_mode='mathml')
    #print renderMath(latex, '/tmp/math', output_mode='png')
    print renderMath(latex, '/tmp/math', output_mode='png', render_engine='texvc')
