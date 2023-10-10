# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

"""main programs - installed via setuptools' entry_points"""

import optparse
import time
import traceback
import webbrowser

import six

from mwlib import expander, wiki
from mwlib.miscellaneous.status import Status
from mwlib.networking.net.podclient import PODClient, podclient_from_serviceurl
from mwlib.refine import uparser
from mwlib.utilities import utils


def show():
    parser = optparse.OptionParser()
    parser.add_option("-c", "--config", help="configuration file/URL/shortcut")
    parser.add_option("-e", "--expand", action="store_true", help="expand templates")
    parser.add_option("-t", "--template", action="store_true", help="show template")
    parser.add_option("-f", help="read input from file. implies -e")

    options, args = parser.parse_args()

    if not args and not options.f:
        parser.error("missing ARTICLE argument")

    articles = [six.text_type(x, "utf-8") for x in args]

    conf = options.config
    if not conf:
        parser.error("missing --config argument")

    wiki_db = wiki.make_wiki(conf).wiki

    for article in articles:
        defaultns = 10 if options.template else 0

        page = wiki_db.normalize_and_get_page(article, defaultns)
        raw = page.rawtext if page else None

        if raw:
            if options.expand:
                template_expander = expander.Expander(raw, pagename=article, wikidb=wiki_db)
                raw = template_expander.expandTemplates()

            print(raw.encode("utf-8"))
    if options.f:
        with open(options.f) as opt_file:
            six.text_type(opt_file.read(), "utf-8")
        template_expander = expander.Expander(raw, pagename="test", wikidb=wiki_db)
        raw = template_expander.expandTemplates()
        print(raw.encode("utf-8"))


def post():
    parser = optparse.OptionParser(usage="%prog OPTIONS")
    parser.add_option("-i", "--input", help="ZIP file to POST")
    parser.add_option("-l", "--logfile", help="log output to LOGFILE")
    parser.add_option("-p", "--posturl", help="HTTP POST ZIP file to POSTURL")
    parser.add_option(
        "-g",
        "--getposturl",
        help="get POST URL from PediaPress.com, open upload page in webbrowser",
        action="store_true",
    )
    options, _ = parser.parse_args()

    use_help = "Use --help for usage information."
    if not options.input:
        parser.error("Specify --input.\n" + use_help)
    if (options.posturl and options.getposturl) or (
        not options.posturl and not options.getposturl
    ):
        parser.error("Specify either --posturl or --getposturl.\n" + use_help)
    if options.posturl:
        podclient = PODClient(options.posturl)
    elif options.getposturl:
        podclient = podclient_from_serviceurl("http://pediapress.com/api/collections/")
        webbrowser.open(podclient.redirecturl)

    if options.logfile:
        utils.start_logging(options.logfile)

    status = Status(podclient=podclient)

    try:
        status(status="uploading", progress=0)
        podclient.post_zipfile(options.input)
        status(status="finished", progress=100)
    except Exception:
        status(status="error")
        raise


def parse_article(article, wiki_db, options):
    try:
        page = wiki_db.normalize_and_get_page(article, 0)
        raw = page.rawtext if page else None
        # yes, raw can be None, when we have a
        # redirect to a non-existing article.
        if raw is None:
            return
        stime = time.time()
        uparser.parse_string(article, raw=raw, wikidb=wiki_db)
    except Exception as err:
        print("F", repr(article), err)
        if options.tb:
            traceback.print_exc()
    else:
        print("G", time.time() - stime, repr(article))


def parse():
    parser = optparse.OptionParser(
        usage="%prog [-a|--all] --config CONFIG [ARTICLE1 ...]"
    )
    parser.add_option("-a", "--all", action="store_true", help="parse all articles")
    parser.add_option("--tb", action="store_true", help="show traceback on error")

    parser.add_option("-c", "--config", help="configuration file/URL/shortcut")

    options, args = parser.parse_args()

    if not args and not options.all:
        parser.error("missing option.")

    if not options.config:
        parser.error("missing --config argument")

    articles = [six.text_type(x, "utf-8") for x in args]

    conf = options.config

    new_wiki = wiki.make_wiki(conf)

    wiki_db = new_wiki.wiki

    if options.all:
        if not hasattr(wiki_db, "articles"):
            raise RuntimeError(f"{wiki_db} does not support iterating over all articles")
        articles = wiki_db.articles()

    for article in articles:
        parse_article(article, wiki_db, options)
