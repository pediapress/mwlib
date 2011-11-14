.. -*- mode: rst; coding: utf-8 -*-

~~~~~~~~~~~~~~~~~~~
command line tools
~~~~~~~~~~~~~~~~~~~

Common Options
==============

This section contains a description of options that are accepted by more than
one command.

``-h, --help``

  Show usage information and exit.

``-c, --config=CONFIG``

  The value for this option describes the source of MediaWiki articles and
  images for the command and can be of one of the following types:

  * A "base URL" of a MediaWiki installation. A base URL is the URL up to, but
    not including the ``index.php``/``api.php`` part.
  
    This URL can differ from
    the prefix seen in "pretty" article URLs. For example the article *Physics*
    in the English Wikipedia has the URL http://en.wikipedia.org/wiki/Physics,
    but the base URL is http://en.wikipedia.org/w/.
  
    If you've set up your own
    MediaWiki you probably know what your base URL should be, but if you're
    using a different MediaWiki, you can see the base URL if add a query string
    to the URL, e.g. by clicking on the edit link or by looking at an older
    revision of an article.
  
    This value for ``--config`` corresponds to ``type=mwapi`` in a configuration
    file (see ``docs/configfiles.txt``), i.e. articles and images are fetched with the
    `MediaWiki API`_. Specifying the URL directly as value for ``--config``
    is usually the quicker way to achieve exactly the same result.
    
    This requires MediaWiki 1.11 or later.
  
  * A shortcut for a base URL. Currently there are the following shortcuts:

    - ":en" -- http://en.wikipedia.org/w/, i.e. the English Wikipedia
    - ":de" -- http://en.wikipedia.org/w/, i.e. the German Wikipedia

  * A filename of a ZIP file generated with the `the mw-zip Command`_.
  
  * A filename of a configuration file (see ``docs/configfiles.txt``).

``-m, --metabook=METABOOK``

  Description of the article collection to be rendered in JSON format.
  This is used by the `Collection extension`_ to transfer this information
  to ``mw-serve`` which in turn passes the information to ``mw-render`` and
  ``mw-zip``.

``--collectionpage=COLLECTIONPAGE``

  Title of a saved article collection (using the `Collection extension`_)

``-x, --no-images``

  If given, no images are included in the output document.

``-i, --imagesize=IMAGESIZE``

  Maximum size (which can be either width or height, whichever is greater) of
  images. If images exceed this maximum size, they're scaled down.  

``--template-blacklist=ARTICLE``

  A name of an article containing a list of "blacklisted templates", i.e.
  MediaWiki templates that should be discarded during rendering.
  Example for such a template blacklist page::

    * [[Template:SkipMe]]
    * [[Template:MeToo]]

``--template-exclusion-category=CATEGORY``

  A name of a category: Templates in this cateogry are excluded during rendering.
  
``--print-template-prefix=PREFIX``

  Prefix for "print templates", i.e. templates that are tried to fetch before
  regular templates. The default value is 'Print' resultint in print template
  names of the form 'Template:PrintNAME' (with NAME being the name of the original
  template).

``-o, --output=OUTPUT``

  Write output to given file.

``-l, --logfile=LOGFILE``

  Log output to the given file.

``--login=USERNAME:PASSWORD[:DOMAIN]``

  For MediaWikis that restrict the viewing of pages, login with given USERNAME,
  PASSWORD and optionally DOMAIN.
  
  Currently this is only supported for mwapidb, i.e. when the --config argument
  is a base URL or shortcut, or when ``type=mwapi`` in the configuration file.

``--title``

  Specify a title for the article collection. This is e.g. used by some writers
  to produce a title page. This title overrides titles contained in ZIP files
  or metabook files.

``--subtitle``

  Specify a subtitle for the article collection. This is e.g. used by some writers
  to produce a title page (note that subtitle might require a tilte).
  This subtitle overrides subtitles contained in ZIP files or metabook files.

The ``mw-render`` Command
=========================

Render MediaWiki articles to one of several output formats like PDF or
OpenDocument Text.

Usage
-----
::

  mw-render [OPTIONS] [ARTICLETITLE...]

Specific Options
----------------

``-w, --writer``

  Name of the writer to produce the output. The list of available writers
  can be seen with ``mw-render --list-writers``.

``--list-writers``

  List the available writers.
  
``-W, --writer-options``

  Writer specific options in a ";" separated list (depending on your shell,
  quoting with "..." or '...' might be needed). Each item in that list can
  either be a single option or an option=value pair. To list the available
  writer options use ``mw-render --writer-info WRITERNAME``.

``--writer-info=WRITER``

  Show available options and some additional information about the given writer.

``-s, --status-file=STATUS_FILE``

  Write status/progress information in JSON format to this file. The file
  is continuously updated during the execution of ``mw-render``.

``-e, --error-file=ERROR_FILE``

  If an error occurs, write the error message to this file. If no error occurs
  this file is not written/created.

``--keep-zip=FILENAME``

  Do not remove the (otherwise temporary) ZIP file, but save it under FILENAME.


The ``mw-zip`` Command
======================

Generate a ZIP file containing

 * articles,
 * images,
 * templates and
 * additional meta information (especially if ``--metabook`` is given, see
   `Common Options`_) like name and URL of the MediaWiki, licensing information
   and title, subtitle and the hierarchical structure of the article collection.

Usage
-----
::

  mw-zip [OPTIONS] [ARTICLETITLE...]
  
Specific Options
----------------

``-p, --posturl=POSTURL``

  Upload the ZIP file with an HTTP POST request to the given URL.

``-g , --getposturl``

  Retrieve the POSTURL from PediaPress and open the upload page in the web
  browser.


The ``mw-post`` Command
=======================

Send a ZIP file generated with `the mw-zip command`_ to a given or an
automatically retrieved URL via HTTP POST request.

Usage
-----
::

  mw-post [OPTIONS]
  
Specific Options
----------------

``-i, --input=INPUT``
  
  Filename of ZIP file.

``-p, --posturl=POSTURL``

  Upload the ZIP file with an HTTP POST request to the given URL.

``-g , --getposturl``

  Retrieve the POSTURL from PediaPress and open the upload page in the web
  browser.



The ``mw-serve-ctl`` command
============================


``--purge-cache=HOURS``

  Remove all cached files in --cache-dir that haven't been touched for the
  last HOURS hours. This is meant to be run as a cron job.

``--clean-up``

  Report errors for processes that have died irregularly.



.. _`MediaWiki API`: http://www.mediawiki.org/wiki/API
.. _`Collection extension`: http://www.mediawiki.org/wiki/Extension:Collection

