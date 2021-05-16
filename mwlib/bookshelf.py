#!/usr/bin/env python

"""
Helper to list and retrieve all stored books from a wiki
"""


from __future__ import absolute_import
from __future__ import print_function


class Bookshelf(object):
    def __init__(self, api):
        self.api = api
        self.coll_bookscategory = "Category:%s" % self.api.content_query(
            "MediaWiki:Coll-bookscategory"
        )

    def _get_category_members(self, title):
        kwargs = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": title,  # FIXME
            "cmlimit": 500,
        }
        res = []  # {ns, title}
        while True:
            r = self.api.do_request(**kwargs)
            res.extend(r["query"].get("categorymembers", []))
            if "query-continue" in r:
                kwargs["cmcontinue"] = r["query-continue"]["categorymembers"]["cmcontinue"]
            else:
                break
        return res

    def booknames(self):
        "returns a list of all book pages"
        return [x["title"] for x in self._get_category_members(self.coll_bookscategory)]


if __name__ == "__main__":
    from mwlib.mwapidb import get_api_helper

    b = Bookshelf(get_api_helper("http://en.wikipedia.org/w/"))
    print("have %d books" % len(b.booknames()))
