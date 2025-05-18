# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

"""main programs - installed via setuptools' entry_points"""


import time
import traceback
import webbrowser

import click
from gevent import monkey

monkey.patch_all()

from mwlib.core import wiki  # noqa: E402
from mwlib.network.podclient import PODClient, podclient_from_serviceurl  # noqa: E402
from mwlib.parser import expander  # noqa: E402
from mwlib.parser.refine import uparser  # noqa: E402
from mwlib.utils import unorganized  # noqa: E402
from mwlib.utils.status import Status  # noqa: E402


@click.command()
@click.option("-c", "--config", required=True, help="Configuration file/URL/shortcut")
@click.option("-e", "--expand", is_flag=True, help="Expand templates")
@click.option("-t", "--template", is_flag=True, help="Show template")
@click.option(
    "-f", type=click.Path(exists=True), help="Read input from file. Implies -e"
)
@click.argument("articles", nargs=-1)
def show(config, expand, template, f, articles):
    if not articles and not f:
        raise click.UsageError("missing ARTICLE argument")

    articles = [str(x, "utf-8") for x in articles]
    wiki_db = wiki.make_wiki(config).wiki

    for article in articles:
        defaultns = 10 if template else 0

        page = wiki_db.normalize_and_get_page(article, defaultns)
        raw = page.rawtext if page else None

        if raw:
            if expand:
                template_expander = expander.Expander(
                    raw, pagename=article, wikidb=wiki_db
                )
                raw = template_expander.expandTemplates()

            print(raw.encode("utf-8"))
    if f:
        with open(f) as opt_file:
            str(opt_file.read(), "utf-8")
        template_expander = expander.Expander(raw, pagename="test", wikidb=wiki_db)
        raw = template_expander.expandTemplates()
        print(raw.encode("utf-8"))


@click.command()
@click.option("-i", "--input", required=True, help="ZIP file to POST")
@click.option("-l", "--logfile", help="Log output to LOGFILE")
@click.option("-p", "--posturl", help="HTTP POST ZIP file to POSTURL")
@click.option(
    "-g",
    "--getposturl",
    is_flag=True,
    help="Get POST URL from PediaPress.com, open upload page in webbrowser",
)
def post(input, logfile, posturl, getposturl):
    if (posturl and getposturl) or (not posturl and not getposturl):
        raise click.UsageError("Specify either --posturl or --getposturl")

    if posturl:
        podclient = PODClient(posturl)
    elif getposturl:
        podclient = podclient_from_serviceurl("http://pediapress.com/api/collections/")
        webbrowser.open(podclient.redirecturl)

    if logfile:
        unorganized.start_logging(logfile)

    status = Status(podclient=podclient)

    try:
        status(status="uploading", progress=0)
        podclient.post_zipfile(input)
        status(status="finished", progress=100)
    except Exception:
        status(status="error")
        raise


def parse_article(article, wiki_db, tb):
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
        if tb:
            traceback.print_exc()
    else:
        print("G", time.time() - stime, repr(article))


@click.command()
@click.option("-a", "--all", is_flag=True, help="Parse all articles")
@click.option("--tb", is_flag=True, help="Show traceback on error")
@click.option("-c", "--config", required=True, help="Configuration file/URL/shortcut")
@click.argument("articles", nargs=-1)
def parse(all, tb, config, articles):
    if not articles and not all:
        raise click.UsageError("missing option.")

    new_wiki = wiki.make_wiki(config)
    wiki_db = new_wiki.wiki

    if all:
        if not hasattr(wiki_db, "articles"):
            raise RuntimeError(
                f"{wiki_db} does not support iterating over all articles"
            )
        articles = wiki_db.get_articles()

    for article in articles:
        parse_article(article, wiki_db, tb)
