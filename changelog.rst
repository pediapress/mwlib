======================================================================
Changelog
======================================================================

mwlib
==========================
2012-01-12 release 0.13.3
--------------------------
- fix pagename when expanding <pages> tag
- handle the case where NAMESPACE is called as a template
- get rid of lxml warnings

2012-01-11 release 0.13.2
--------------------------
- add support for adding spacing for cjk text
- add initial support for the pages tag
- protect page-break info from removal in divs and spans

2011-12-13 release 0.13.1
--------------------------
- replaced mw-serve with nserve.py
- removed CGI support
- removed lots of obsolete code
- updated documentation, available online at http://mwlib.readthedocs.org

2011-10-24 release 0.12.17
--------------------------
- handle siteinfo without "magicwords" key in templ.parser
- use gevent instead of twisted in mw-zip/mw-render
- show memory usage in mw-zip
- use sqlite3dmb to store html
- fix directionality of math nodes for RTL documents

2011-08-31 release 0.12.16
--------------------------
- remove xhtmlwriter
- remove docbookwriter
- fix_wikipedia_siteinfo for kdb, ltg and xmf
- remove zipwiki
- implement safesubst
- match noinclude and onlyinclude tags with whitespace
- bail out when running setup.py with an unsupported python version

2011-08-12 release 0.12.15
--------------------------
- require lxml.
- dont switch fonts for direction switch chars lrm/rlm
- set teletype style by css
- fix rtl direction check bug
- quick fix in order to support the kbd tag.
- fix switch statements with localized #default case.
- dont remove direction switching nodes
- resolve aliases when expanding templates.
- support localized parser functions.
- make tests work with latest py.test 2.1.
- add support for css direction switching
- Code and Var nodes now use teletype style
- be more verbose when collection params can not be retrieved
- fix subpage links (bugzilla #28055)
- fix for https://bugzilla.wikimedia.org/show_bug.cgi?id=29354
- dont die on treecleaner errors
- remove paragraphs from galleries
- add license templates
- get rid of some more parsing calls
- cache img display info in licensehandler
- speed up getting template args (for licensehandling)
- always show full text of contributors of images
- fix for getAllDisplayText
- add nofilter to licensehandling
- make licensechecker less fragile to bad config format
- improve image license handling
- improve stats for licensechecker
- add custom element to metabook
- dont throw away collapsible boxes. fixes: #935
- decrease api_request_limit
- limit max. simultaneous img downloads to 15
- moar categories. less whitespace. untangle revision/category fetching
- increase standard resolution of images
- fix getting html with revisions
- clean up after fixNesting
- fetch extension images
- prevent adding same api url twice
- retry failed img downloads
- workaround for missing descriptionurl
- fix: descriptionurl returned from api seems be "false" sometimes.
- fix for #925. make syntaxhighlighting work again
- fix for #755
- support older mediawikis
- add lower bound on word splitting hints
- mwlib.refine: parse <caption> tags inside tables
- be more generous when trying to detect see also
- fix for "See Also "Section removal
- fix #905: remove See also sections.
- remove edit links
- magics.py: handle second argument to fullurl magic function.
- convert tiff images to png
- fix for infobox detection
- handle Abbreviation node in xhtmlwriter
- add Abbreviation node
- improve table splitting

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
- initial release
