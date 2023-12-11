#! /usr/bin/env python

# Copyright (c) 2007, PediaPress GmbH
# See README.txt for additional licensing information.

import optparse
import sys

import simplejson

from mwlib import metabook


def main():
    optparser = optparse.OptionParser(
        usage="%prog [-o OUTPUT] [-t TITLE] [-s SUBTITLE] ARTICLE [...]"
    )
    optparser.add_option("-o", "--output", help="write output to file OUTPUT")
    optparser.add_option("-t", "--title", help="use given TITLE")
    optparser.add_option("-s", "--subtitle", help="use given SUBTITLE")
    options, args = optparser.parse_args()

    if not args:
        sys.exit("No article given.")

    title = None
    if options.title:
        title = str(options.title, "utf-8")
    subtitle = None

    if options.subtitle:
        subtitle = str(options.subtitle, "utf-8")

    meta_book = metabook.collection(title=title, subtitle=subtitle)
    for title in args:
        meta_book["items"].append(metabook.article(title=str(title, "utf-8")))

    if options.output:
        with open("test.json", "w") as test_file:
            test_file.write(simplejson.dumps(meta_book))
    else:
        output_file = sys.stdout
        output_file.write(simplejson.dumps(meta_book))


if __name__ == "__main__":
    main()
