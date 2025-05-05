#! /usr/bin/env python

# Copyright (c) 2007, PediaPress GmbH
# See README.txt for additional licensing information.

import sys

import click
import simplejson

from mwlib.core import metabook


@click.command()
@click.option('-o', '--output', type=click.Path(writable=True), help="Write output to file OUTPUT")
@click.option('-t', '--title', help="Use given TITLE")
@click.option('-s', '--subtitle', help="Use given SUBTITLE")
@click.argument('articles', nargs=-1)
def main(output, title, subtitle, articles):

    if not articles:
        sys.exit("No article given.")

    title = title if title else None
    subtitle = subtitle if subtitle else None

    meta_book = metabook.Collection(title=title, subtitle=subtitle)
    for article_title in articles:
        meta_book["items"].append(metabook.Article(title=str(article_title, "utf-8")))

    if output:
        with open(output, "w") as output_file:
            output_file.write(simplejson.dumps(meta_book))
    else:
        sys.stdout.write(simplejson.dumps(meta_book))

if __name__ == "__main__":
    main()
