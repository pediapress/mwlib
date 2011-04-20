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
Starting with version 0.12.11 released in december 2009 mwlib does not
support python 2.4 anymore. Please use an older version of mwlib or
upgrade your python installation to 2.6 (or 2.5). python 3.x is
currently not supported.

You need to have setuptools/easy_install installed. Installation
should be as easy as typing::
  
  $ easy_install mwlib

If you don't have setuptools installed, download the source package, 
unpack it and run::

  $ python setup.py install

(this will also install setuptools)

You can also install the latest `mwlib development version`_ with::

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

Changelog
======================================================================
2010-10-29 release 0.12.14
--------------------------
- magics.py: fix NS magic function.
- refine/core.py: do not parse links if link target would contain newlines.
- setup.py: require lockfile==0.8.
- add xr formatting in #time
- replace mwlib.async with qserve package.
- move fontswitcher to writer dir
- remove collapsible elements
- fix for #830
- move gallery nodes out of tables.
- handle overflow:auto crap
- fix for reference handling
- better handling for references nodes.
- fix for ReferenceLists
- fix whitespace handling and implicit newlines in template arguments. fixes http://code.pediapress.com/wiki/ticket/877.
- Add support for more PageMagic as per http://meta.wikimedia.org/wiki/Help:Magic_words
- Fix PageMagic to consider page as argument
- fetch parsed html from mediawiki and store it as parsed_html.json. We store the raw result from mediawiki since it's not clear what's really needed.
- make mwapi work for non query actions.

2010-7-16 release 0.12.13
--------------------------
- omit passwords from error file
- make login work with latest mediawiki.
- use content_type, not content-type in metabooks
- filter crap from ref node names
- try to set GDFONTPATH to some sane value. call EasyTimeline with font argument.
- do not scale easytimeline images after rendering rather scale then in EasyTimeline.pl
- update EasyTimeline to 1.13
- another fix for nested references
- fix for broken tables
- make #IFEXIST handle images
- add treecleaner method to avoid large cells
- fix img alignment
- fix nesting of section with same level
- do not let tablemode get negative.
- fix #815
- call fix_wikipedia_siteinfo based on contents of server (instead of sitename)
- workaround for broken interwikimap. fixes #807
- handle the case, where the <br> ends up in a new paragraph. fixes #804
- move the poem tag implementation to mwlib.refine.core and make it expand templates
- add #ifeq node. fixes #800
- fix for images with spaces in file extensions
- fix and test for #795
- pull tables out of DefinitionDescriptions
- add getVerticalAlign to styleutils
- remove tables from image captions
- remove --clean-cache option to mw-serve
- allow floats as --purge-cache argument
- workaround for buggy lockfile module.
- implement DISPLAYTITLE
- generate higher resolution timelines
- handle abbr and hiero tags
- make sure print_template_pattern is written to nfo.json, when
  getting it as part of the collection params
- relax odfpy requirement a bit
- make hash-mark only links work again
- remove empty images

2009-12-16 release 0.12.12
--------------------------
- dont remove sections containing only images.
- improve handling of galleries
- fix use of uninitialized last variable
- do not 'split' links when expanding templates
- quick workaround for http://code.pediapress.com/wiki/ticket/754

2009-12-8 release 0.12.11
-------------------------
- *beware* python 2.4 is not supported anymore
- parse paragraphs before spans
- parse named urls before links. 
- fix urllinks inside links
- fix named urls inside double brackets
- avoid splitting up Reference nodes. 
- parse lines/lists before span.
- add getScripts method. improve rtl compat. for fontswitching
- do not replace uniq strings with their content when preprocessing gallery tags. fixes e.g. ref tags inside gallery tags.
- run template expansion for each line in gallery tags
- handle mhr, ace, ckb, mwl interwiki links
- add clearStyles method
- add another condition to avoid single col tables in border-boxes
- refactor node style handling
- remove fixInfoBoxes from treecleaner
- fix for identifiying image license information
- handle closing ul/ol tags inside enumerations
- correctly determine text alignment of node.
- fix for image only table check
- add code for simple rpc servers/clients based on the gevent library.
- add flag for split itemlists
- do not blacklist articles
- add upper limit for font sizes


2009-10-20 release 0.12.10
--------------------------
- fix race condition when fetching siteinfo
- introduce flag to suppress automatic escaping when cleaning text
- sent error mails only once
- add 'pageby', 'uml', 'graphviz', 'categorytree', 'summary' to list
  of tags to ignore 

2009-10-13 release 0.12.9
-------------------------
- fix #709
- allow higher resolution in math formulas
- fetch collection parameters and use them (template exclusion category,...)
- fix #699
- fix <ref> inside table caption
- refactor filequeue
- adjust table splitting parameter
- move invisible, named references out of table nodes
- fix late #if
- fix bug with inputboxes
- fix parsing of collection pages: titles/subtitles may but do not need to have spaces
- use new default license URL
- fix race condition in mw-serve/mw-watch

2009-9-25 release 0.12.8
------------------------
- fix argument handling in mw-serve
  Previously it had been possible to overwrite any file by passing
  arguments containing newlines to mw-serve.

2009-9-23 release 0.12.7
------------------------
- ensure that files extracted from zip files end up in the destination
  directory.

2009-9-15 release 0.12.6
------------------------
- fix for reference nodes
- allow most characters in urls
- fix for setting content-length in response
- fix problem with blacklisted templates creating preformatted nodes (#630)
- do not split preformatted nodes on non-empty whitespace only lines
- do not create preformatted nodes inside li tags
- pull garbage out of table rows. fix #17.
- dont remove empty spans if an explicit size is given.
- uncomment fix_wikipedia_siteinfo and add pnb as interwiki link
- remove mwxml writer. 
- add mw-version program

2009-9-8 release 0.12.5
------------------------
- fix missing page case in get_page when looking for redirects
- some minor bugfixes

2009-8-25 release 0.12.3
------------------------
- better compatibility with older mediawiki installations

2009-8-18 release 0.12.2
------------------------
- fix status callbacks to pod partner

2009-8-17 release 0.12.1
------------------------
- added mw-client and mw-check-service
- mw-serve-ctl can now send report mails
- fixes for race conditions in mwlib.filequeue (mw-watch)
- lots of other improvements...

2009-5-6 release 0.11.2
-----------------------
- fixes

2009-5-5 release 0.11.1
------------------------
- merge of the nuwiki branch: better, faster resource fetching with twisted_api,
  new ZIP file format with nuwiki

2009-4-21 release 0.10.4
------------------------
- fix chapter handling
- fix bad #tag params

2009-4-17 release 0.10.3
------------------------
- fix issue with self-closing tags
- fix issue with "disappearing" table rows

2009-4-15 release 0.10.2
------------------------
- fix for getURL() method in zipwiki

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
.. _mwlib development version: http://code.pediapress.com/git/mwlib/?p=mwlib;a=snapshot;h=HEAD;sf=tgz#egg=mwlib-dev
