.. -*- mode: rst; coding: utf-8 -*-

======================================================================
mwlib - MediaWiki parser and utility library
======================================================================


Overview
======================================================================
mwlib provides a library for parsing MediaWiki_ articles.
It is currently aimed at developers, who have a need to somehow handle
MediaWiki articles.

Installation
======================================================================
You need to have setuptools/easy_install installed. Installation
should be as easy as typing::
  
  $ easy_install mwlib

If you don't have setuptools installed, download the source package, 
unpack it and run::

  $ python setup.py install

(this will also install setuptools)

You can also install the latest `mwlib tip`_ with::

  $ easy_install mwlib==dev

(However, you need to have re2c installed for that to work).


You will also need:

*LaTeX*
  LaTeX is used for rendering of mathematical formulas.

*perl*
  perl is used to drive the ``EasyTimeline.pl`` script, which produces
  timeline images.

*PIL*
 PIL_ is the Python Imaging Library and is used for image handling.

*lxml*
 lxml_ is needed for the docbookwriter.

*blahtexml*
 Blahtex is a program written in C++, which converts an equation given
 in a syntax close to TeX into MathML. It is designed by David Harvey
 and is aimed at supporting equations in MediaWiki. 
 (http://gva.noekeon.org/blahtexml/)

*texvc*
  texvc (TeX validator and converter) is a program which validates
  (AMS) LaTeX mathematical expressions and converts them to HTML,
  MathML, or PNG graphics. (see http://en.wikipedia.org/wiki/Texvc).


Commands
======================================================================
The commands (i.e. command-line tools) provided by mwlib are described
in ``docs/commands.txt``.

Configuration
======================================================================
The format of configuration files is described in
``docs/configfiles.txt``.

See ``example_conf.py`` for an example configuration.

Contact/Further Information
======================================================================
For further information please visit our Trac instance running at
http://code.pediapress.com/.
The current development version can also be found there.

Credits
======================================================================
``mwlib/cdb.py`` is based on the cdb implementation from the SpamBayes_
project ((C) 2002-2004 Python Software Foundation).
The remaining parts are distributed under the BSD license:

ChangeLog
======================================================================
2009-4-9 release 0.10.1
-----------------------
- the parser has been completely rewritten (mwlib.refine)
- fix bug in recorddb.py: do not overwrite articles
- removed mwapidb.WikiDB.getTemplatesForArticle() which was broken and
  wasn't used.

2009-3-5 release 0.9.13
-------------------------
- normalize template names when checking against blacklist
- make NAMESPACE magic work for non-main namespaces
- make NS template work

2009-03-02 release 0.9.12
-------------------------
- fix template expansion bug with non self-closing ref tags containing
  equal signs

2009-2-25 release 0.9.11
--------------------------------
- added --print-template-pattern
- fix bug in LOCALURLE with non-ascii characters (#473)
- fix 'upright' image modifier handling (#459)
- allow star inside URLs (#483)
- allow whitespace in image width modifiers (#475) 

2009-2-19 release 0.9.10
--------------------------------
- do not call check() in zipcreator: better some missing articles than an error message

2009-2-18 release 0.9.8
--------------------------------
- localize image modifiers
- fix bug in serve with forced rendering
- fix bug in writerbase when no URL is returned
- return only unqiue image contributors, sorted
- #expr with whitespace only argument now returns the empty string
  instead of marking the result as an error.
- added mw-serve-ctl command line tool (#447)
- mwapidb: omit title in URLs with oldid
- mwapidb: added getTemplatesForArticle() 
- zipcreator: check articles and sources to prevent broken ZIP files
- mwapidb: do query continuation to find out all authors (#420)
- serve: use a deterministic checksum for metabooks (#451)

2009-2-9 release 0.9.7
--------------------------------
- fix bug in #expr parsing
- fix bug in localised namespace handling/#ifexist
- fix bug in redirect handling together with specific revision in mwapidb

2009-2-3  release 0.9.6
--------------------------------
- mwapidb: return authors alphabetically sorted (#420)
- zipcreator: fixed classname from DummyScheduler to DummyJobScheduler; this bug
  broke the --no-threads option
- serve: if rendering is forced, don't re-use ZIP file (#432)
- options: remove default value "Print" from --print-template-prefix
- mapidb: expand local* functions, add them to source dictionary
- expander: fix memory leak in template parser (#439)
- expander: better noinclude, includeonly handling (#426)
- expander: #iferror now uses a regular expression (#435)
- expander: workaround dateutils bug
  (resulting in a TypeError: unsupported operand type(s) for +=: 'NoneType' and 'int')

2009-1-26 release 0.9.5
--------------------------------

License
======================================================================
Copyright (c) 2007-2009 PediaPress GmbH

All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are
met:

* Redistributions of source code must retain the above copyright
  notice, this list of conditions and the following disclaimer.

* Redistributions in binary form must reproduce the above
  copyright notice, this list of conditions and the following
  disclaimer in the documentation and/or other materials provided
  with the distribution. 

* Neither the name of PediaPress GmbH nor the names of its
  contributors may be used to endorse or promote products derived
  from this software without specific prior written permission. 

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
"AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR
CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

.. _MediaWiki: http://www.mediawiki.org/
.. _SpamBayes: http://spambayes.sourceforge.net/
.. _PIL: http://www.pythonware.com/products/pil/
.. _lxml: http://codespeak.net/lxml/
.. _mwlib tip: http://code.pediapress.com/hg/mwlib/archive/tip.tar.gz#egg=mwlib-dev
