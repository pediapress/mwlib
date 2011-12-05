====================================
*Collection* Extension for MediaWiki
====================================

About the *Collection* Extension
================================

The *Collection* extension for MediaWiki_ allows users to collect articles and
generate downloadable version in different formats (PDF, OpenDocument Text etc.)
for article collections and single articles.

The extension has been developed for and tested with MediaWiki_ version 1.14
and later. Some features may not be available with older MediaWikis that
don't have the `MediaWiki API`_ enabled.

The extension is being developed under the GNU General Public License by
`PediaPress GmbH`_ in close collaboration with `Wikimedia Foundation`_
and the `Commonwealth of Learning`_.

Copyright (C) 2008-2011, PediaPress GmbH

Prerequisites
=============

If you use a render server the `MediaWiki API`_ must be enabled
(i.e. just don't override the default value of ``true`` for
``$wgEnableApi`` in your ``LocalSettings.php``).

Install PHP with cURL support
-----------------------------

Currently Collection extension needs PHP with cURL support,
see http://php.net/curl

Installation and Configuration of the Collection Extension
==========================================================

* Download the Collection extension matching your mediawiki version from
  http://www.mediawiki.org/wiki/Special:ExtensionDistributor/Collection
  and unpack it into your mediawiki extensions directory::

    cd /srv/http/wiki/extensions
    tar -vxzf ~/Downloads/Collection-MW1.17-r85033.tar.gz

* Put this line in your ``LocalSettings.php``::

    require_once("$IP/extensions/Collection/Collection.php");

If you intend to use the public render server, you're now ready to go.


Install and Setup a Render Server
---------------------------------

Rendering and ZIP file generation is done by a server, which can run
separately from the MediaWiki installation and can be shared by
different MediaWikis.

If you have a low-traffic MediaWiki you can use the public render
server running at http://tools.pediapress.com/mw-serve/. In this case,
just keep the configuration variable $wgCollectionMWServeURL (see
below) at its default value.

If you can't use the public render server, you'll have to
:ref:`install mwlib <mwlib-install>` and
:ref:`run your own render server <mwlib-renderserver>`.


.. _mwlib: http://code.pediapress.com/wiki/wiki/mwlib
.. _MediaWiki: http://www.mediawiki.org/
.. _`PediaPress GmbH`: http://pediapress.com/
.. _`Wikimedia Foundation`: http://wikimediafoundation.org/
.. _`Commonwealth of Learning`: http://www.col.org/
.. _`MediaWiki API`: http://www.mediawiki.org/wiki/API
.. _`Meta-Wiki`: http://meta.wikimedia.org/wiki/Book_tool/Help/Books
