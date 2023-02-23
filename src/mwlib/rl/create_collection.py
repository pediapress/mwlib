#! /usr/bin/env python
#! -*- coding:utf-8 -*-

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

    mb = metabook.make_metabook(title=title, subtitle=subtitle)
    for title in args:
        mb["items"].append(metabook.make_article(title=str(title, "utf-8")))

    if options.output:
        f = open(options.output, "w")
    else:
        f = sys.stdout

    f.write(simplejson.dumps(mb))


if __name__ == "__main__":
    main()
