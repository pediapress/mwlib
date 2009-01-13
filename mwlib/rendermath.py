#! /usr/bin/env python

# Copyright (c) 2007-2009 PediaPress GmbH
# See README.txt for additional licensing information.

import os
import re
try:
    from hashlib import md5
except ImportError:
    from md5 import md5
    
from mwlib import texmap
import mwlib.log

log = mwlib.log.Log("rendermath")

latex = r"""
%% %(ident)s
\documentclass[%(fontsize)spt]{article}
%(extra_header)s
\usepackage{ucs}
\usepackage{amsmath}
\usepackage{amsfonts}
\usepackage{amssymb}

%% \newcommand{\R}[0]{\mathbb{R}}

\def\Alpha{{A{}}}
\def\Beta{{B{}}}
\def\Epsilon{{E{}}}
\def\Zeta{{Z{}}}
\def\Eta{{H{}}}
\def\Iota{{I{}}}
\def\Kappa{{K{}}}
\def\Mu{{M{}}}
\def\Nu{{N{}}}
\def\Rho{{P{}}}
\def\Tau{{T{}}}
\def\Chi{{C{}}}

\usepackage[utf8x]{inputenc}
\usepackage[dvips]{graphicx}
\pagestyle{empty}
\begin{document}
%(source)s
\end{document}
"""






def mysystem(cmd):
    err=os.system(cmd)
    if err:
        raise RuntimeError("exit code %s while running %r" % (err, cmd))
        
class Renderer(object):
    basedir = os.path.expanduser("~/pngmath/")
    
    def __init__(self, basedir=None, lazy=True):
        if basedir:
            self.basedir = os.path.realpath(os.path.join(basedir, 'pngmath/'))
        if not os.path.exists(self.basedir):
            os.makedirs(self.basedir)
        self.lazy = lazy
    
    def _render_file(self, name, format):
        assert format in ('pdf', 'png', 'eps'), "rendermath: format %r not supported" % format

        texfile = os.path.join(self.basedir, name+'.tex')
        srcbase = os.path.join(self.basedir, name)

        cwd = os.getcwd()
        os.chdir(self.basedir)
        try:
            mysystem("latex -interaction=batchmode %s" % texfile)
            mysystem("dvips -E %s.dvi -o %s.ps" % (srcbase, srcbase))
            if format=='png':
                mysystem("convert +adjoin -transparent white -density 300x300 %s.ps %s.png" % (srcbase, srcbase))
            elif format=='pdf':
                mysystem("epstopdf %s.ps" % srcbase)
            elif format=='eps':
                os.rename("%s.ps" % srcbase, "%s.eps" % srcbase)
        finally:
            for x in ['.dvi', '.aux', '.log', '.ps']:
                p = os.path.join(self.basedir, name+x)
                try:
                    os.unlink(p)
                except OSError, err:
                    pass

            os.chdir(cwd)

    def _normalizeLatex(self, latexsource):
        latexsource = re.compile("\n+").sub("\n", latexsource)
        return latexsource
    
    def convert(self, latexsource, lazy=True, format='pdf', addMathEnv=True):
        assert format in ('pdf', 'png', 'eps'), "rendermath: format %r not supported" % format
        latexsource = self._normalizeLatex(latexsource)
        if addMathEnv:
            latexsource = '$' + latexsource + '$'
        if format in ('pdf', 'eps'):
            extra_header = '\usepackage{geometry}\n\geometry{textwidth=3.0in}\n'
            fontsize = 10
        else:
            fontsize = 12
            extra_header = ''

        latexsource = texmap.convertSymbols(latexsource)
        
        source = latex % dict(source=latexsource,
                              ident=format,
                              fontsize=fontsize,
                              extra_header=extra_header)
            
        m=md5()
        m.update(source)
        name = m.hexdigest()

        srcbase = os.path.join(self.basedir, name)
        texfile = os.path.join(self.basedir, name+'.tex')
        outfile = os.path.join(self.basedir, name+'.'+format)
        
        if os.path.exists(outfile):
            return outfile  #  FIXME
        
        open(texfile, 'w').write(source)

        if not lazy:
            self._render_file(name, format)
            
            
        return outfile

    def render(self, latexsource, lazy=None, addMathEnv=True):
        if lazy is None:
            lazy = self.lazy
        return self.convert(latexsource, lazy=lazy, format='png', addMathEnv=addMathEnv)
    
