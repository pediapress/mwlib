#! /usr/bin/env python

# Copyright (c) 2007-2009 PediaPress GmbH
# See README.txt for additional licensing information.

import re


class inspect_authors(object):
    ip_rex = re.compile(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$')
    bot_rex = re.compile(r'bot', re.IGNORECASE)

    def get_authors(self, revs):
        """Return names of non-bot, non-anon users for changes of
        given article (before given revision).

        The data that can be used to compute a list of authors is
        limited:
        http://de.wikipedia.org/w/api.php?action=query&prop=revisions&rvlimit=500&
        rvprop=ids|timestamp|flags|comment|user|size&titles=Claude_Bourgelat

        @returns: sorted list of principal authors
        @rtype: list([unicode])
        """

        if not revs:
            return []

        def mycmp(r1, r2):
            return cmp(r1.get("revid"), r2.get("revid"))

        revs.sort(cmp=mycmp)

        ANON = "ANONIPEDITS"
        authors = dict()  # author:bytes
        for r in revs:
            if 'minor' in r:
                pass  # include minor edits
            user = r.get('user', u'')
            if 'anon' in r and (not user or self.ip_rex.match(user)):  # anon
                authors[ANON] = authors.get(ANON, 0) + 1
            elif not user:
                continue
            elif self.bot_rex.search(user) or self.bot_rex.search(r.get('comment', '')):
                continue  # filter bots
            else:
                authors[user] = authors.get(user, 0) + 1

        num_anon = authors.get(ANON, 0)
        try:
            del authors[ANON]
        except KeyError:
            pass

        authors = authors.items()
        authors.sort()

        # append anon
        authors.append((("%s:%d" % (ANON, num_anon), num_anon)))  # append at the end
    #        print authors
        return [a for a, c in authors]

get_authors = inspect_authors().get_authors
