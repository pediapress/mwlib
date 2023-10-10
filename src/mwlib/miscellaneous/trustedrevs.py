#! /usr/bin/env python


import time

import mwclient
import six.moves.urllib.error
import six.moves.urllib.parse
import six.moves.urllib.request

from mwlib.consts.urls import WIKITRUST_API


class WikiTrustServerError(Exception):
    "For some reason the API often respons with an error"
    msg_identifier = "EERROR detected.  Try again in a moment, or report an error on the WikiTrust bug tracker."


class TrustedRevisions:
    min_trust = 0.80
    wikitrust_api = WIKITRUST_API

    def __init__(self, site_name="en.wikipedia.org"):
        self.site = mwclient.Site(site_name)

    def get_wiki_trust_score(self, title, revid):
        # http://en.collaborativetrust.com/WikiTrust/RemoteAPI?method=quality&title=Buster_Keaton&pageid=43055&revid=364710354
        url = "%s?method=quality&title=%s&revid=%d" % (
            self.wikitrust_api,
            six.moves.urllib.parse.quote(title),
            revid,
        )
        rev= six.moves.urllib.request.urlopen(url).read()
        if rev == WikiTrustServerError.msg_identifier:
            raise WikiTrustServerError
        return 1 - float(rev)  # r is the likelyhood of being spam

    def _update_wiki_revision_with_trust_score(self, rev, now, title):
        # add basic info
        rev["age"] = (now - time.mktime(rev["timestamp"])) / (24 * 3600)
        rev["title"] = title
        # don't use bot revs
        if "bot" in rev["user"].lower():
            return
        # don't use reverted revs (but rather the original one)
        if "revert" in rev.get("comment", "").lower():
            return
        try:
            rev["score"] = self.get_wiki_trust_score(title, rev["revid"])
        except WikiTrustServerError:
            return

    def get_trusted_revision(self, title, min_trust=None, max_age=None):
        min_trust = min_trust or self.min_trust
        best_rev = None
        now = time.time()
        page = self.site.Pages[title]
        for rev in page.revisions():
            self._update_wiki_revision_with_trust_score(rev, now, title)

            if not best_rev or rev["score"] > best_rev["score"]:
                best_rev = rev
            if rev["score"] > min_trust:  # break if we have a sufficient score
                break
            if max_age and rev["age"] > max_age:  # article too old
                break

        return best_rev


if __name__ == "__main__":
    import sys

    tr = TrustedRevisions()
    trev = tr.get_trusted_revision(sys.argv[1])
    print("Found revision:", trev)
    title = trev["title"]
    rev = trev["revid"]
    age = trev["age"]
    print(
        f"title:{title} revid:{rev} age:{'%.2f' % age}"
    )
