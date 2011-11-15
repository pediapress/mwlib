Metabooks
==============

A Metabook describes a collection of articles and chapters together with some
metadata like title or version. The actual data (e.g. the wikitext of
articles) is not contained in the Metabook.

The Metabook is a simple dictionary containing lists, integers, strings (which
are Unicode-safe; they are represented as unicode in Python) and other
dictionaries. When read from/written to a file or sent over the network, it"s
serialized in `JSON`_ format.


Metabook Types
---------------

Every dictionary contained in the Metabook (and the Metabook dicionary itself)
has a type. The different types are described below. The Metabook dictionary
itself has type "collection".

Collection
----------

type (string):

    Fixed value "collection"

version (integer):

    Protocol version, 1 for now

title (string, optional):

    Title of the collection

subtitle (string, optional):

    Subtitle of the collection

editor (string, optional):

    Editor of the collection

items (list of `article`_ and/or `chapter`_ objects, can be empty):

    Chapters and top-level articles contained in the collection
    
licenses (list of `license`_ objects):

    List of licenses for articles in this collection


License
-------

type (string)

    Fixed value "license"

name (string)

    Name of license

mw_license_url (string, optional)

    URL to license text in wikitext format

mw_rights_page (string, optional)

    Title of article containing license text

mw_rights_icon (string, optional)

    URL of license icon

mw_rights_url (string, optional)

    URL to license text in any format

mw_rights_text (string, optional)

    Name and possibly a short description of the license


Article
-------

type (string):

    Fixed value "article"

content_type (string):

    Fixed value "text/x-wiki"

title (string):

    Title of this article

displaytitle (string, optional):

    Title to be used in rendered output instead of the real title

revision (string, optional):

    Revision of article, i.e. oldid for MediaWiki. If omitted, the latest
    revision is used.

timestamp (integer, optional):

    UNIX timestamp (seconds since 1970-1-1) of the revision of this article
    
url (string):

    URL to article in source wiki

authors (list of strings):

    list of principal authors

source-url (string)

    URL of source wiki. This URL is the key to an item in the sources dictionary
    in the content.json object of the ZIP file.


Chapter
-------

type (string):

    Fixed value "chapter"

title (string):

    Title of this chapter

items (list of `article`_ objects, can be empty):

    List of articles contained in this chapter


Source
------
        
type (string)

    Fixed value "source"

system (string):

    Fixed value "MediaWiki" for now

url (string, optional):

    "home" URL of source, e.g. "http://en.wikipedia.org/wiki/Main_Page"
    (same as key for this entry)

name (string):

    Unique name of source, e.g. "Wikipedia (en)"

language (string)

    2-character ISO code of language, e.g. "en"

interwikimap (dictionary mapping prefixes to `interwiki`_ objects, optional)

    Describes interwikimap for this wiki,
    cf. http://en.wikipedia.org/w/api.php?action=query&meta=siteinfo&siprop=interwikimap


Interwiki
---------

Interwiki entries can describe language links and interwiki links

type (string)

    Fixed value "interwiki"

prefix (string)

    Prefix is MediaWiki links, i.e. the part before the ":".
    This is the key in the interwikimap attribute of a `source`_ object.

url (string)

    URL template, the string "$1" gets replaced with the link target (w/out prefx)

local (bool, optional)

    True if the interwiki link is a "local" one

language (string, optional)

    Name of the language, if this interwiki describes language links



Example
-----------------

Given in `JSON`_ notation::

    {
        "type": "collection",
        "version": 1,
        "title": "This is the Collection Title",
        "subtitle": "An optional subtitle",
        "editor": "Jane Doe",
        "items": [
            {
                "type": "article",
                "title": "Top-level Article",
                "content_type": "text/x-wiki"
            },
            {
                "type": "chapter",
                "title": "First Chapter",
                "items": [
                    {
                        "type": "article",
                        "title": "First Article in Chapter",
                        "revision": "1234",
                        "timestamp": 122331212312,
                        "content_type": "text/x-wiki"
                        "source-url": "http://en.wikipedia.org/wiki/Main_Page",
                    },
                    {
                        "type": "article",
                        "title": "Second Article in Chapter",
                        "content_type": "text/x-wiki"
                        "source-url": "http://en.wikipedia.org/wiki/Main_Page",
                    }
                ]
            },
        ],
        "licenses": [
            {
                "type": "license",
                "name": "GFDL",
                "mw_license_url": "http://en.wikipedia.org/wiki/Wikipedia:Text_of_the_GNU_Free_Documentation_License"
            }
        ]
    }

.. _`JSON`: http://json.org/
