#! /usr/bin/env python

# Copyright (c) 2007-2011 PediaPress GmbH
# See README.rst for additional licensing information.

import re


class inspect_authors(object):
    ip_rex = re.compile(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$')
    bot_rex = re.compile(r'bot', re.IGNORECASE)
    ANON = "ANONIPEDITS"

    def __init__(self):
        self.num_anon = 0
        self.authors = set()

    def scan_edits(self, revs):
        authors = self.authors

        for r in revs:
            user = r.get('user', u'')
            if 'anon' in r and (not user or self.ip_rex.match(user)):  # anon
                self.num_anon += 1
            elif not user:
                continue
            elif self.bot_rex.search(user) or self.bot_rex.search(r.get('comment', '')):
                continue  # filter bots
            else:
                authors.add(user)

    def get_authors(self):
        """Return names of non-bot, non-anon users for changes of
        given article (before given revision).

        The data that can be used to compute a list of authors is
        limited:
        http://de.wikipedia.org/w/api.php?action=query&prop=revisions&rvlimit=500&
        rvprop=ids|timestamp|flags|comment|user|size&titles=Claude_Bourgelat

        @returns: sorted list of principal authors
        @rtype: list([unicode])
        """

        authors = list(self.authors)
        authors.sort()
        if authors or self.num_anon:
            authors.append("%s:%d" % (self.ANON, self.num_anon))  # append anon
        return authors


def get_authors(revs):
    i = inspect_authors()
    i.scan_edits(revs)
    return i.get_authors()
