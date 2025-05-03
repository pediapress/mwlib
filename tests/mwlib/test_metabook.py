#! /usr/bin/env py.test

from mwlib.core import metabook
from mwlib.utils import myjson as json

ARTICLE1 = "Article 1"
ARTICLE2 = "Article 2"
ARTICLE3 = "Article 3"
CHAPTER1 = "Chapter 1"
CHAPTER2 = "Chapter 2"
TEXT_X_WIKI = "text/x-wiki"

test_wikitext1 = """== Title ==
=== Subtitle ===
{{Template}}

Summary line 1
Summary line 2

;Chapter 1
:[[Article 1]]
:[[:Article 2]]

;Chapter 2
:[[Article 3|Display Title 1]]
:[{{fullurl:Article 4|oldid=4}}Display Title 2]

"""

test_wikitext2 = """== Title ==
=== Subtitle ===
{{
Template
}}

Summary line 1
Summary line 2

;Chapter 1
:[[Article 1]]
:[[:Article 2]]

;Chapter 2
:[[Article 3|Display Title 1]]
:[{{fullurl:Article 4|oldid=4}}Display Title 2]

"""

test_metabook = {
    "type": "collection",
    "version": 1,
    "title": "bla",
    "items": [
        {
            "type": "Chapter",
            "title": CHAPTER1,
            "items": [
                {
                    "type": "article",
                    "title": ARTICLE1,
                    "content_type": TEXT_X_WIKI,
                },
                {
                    "type": "article",
                    "title": ARTICLE2,
                    "content_type": TEXT_X_WIKI,
                },
            ],
        },
        {
            "type": "Chapter",
            "title": CHAPTER2,
            "items": [
                {
                    "type": "article",
                    "title": ARTICLE3,
                    "displaytitle": "Display Title",
                    "content_type": TEXT_X_WIKI,
                },
            ],
        },
    ],
}

test_metabook = json.loads(json.dumps(test_metabook))


def test_parse_collection_page():
    def verify_items(items):
        assert len(items) == 2
        assert items[0].type == "Chapter"
        assert items[0].title == CHAPTER1
        arts = items[0].items
        assert len(arts) == 2
        assert arts[0].type == "article"
        assert arts[0].title == ARTICLE1
        assert arts[1].type == "article"
        assert arts[1].title == ARTICLE2
        assert items[1].type == "Chapter"
        assert items[1].title == CHAPTER2
        arts = items[1].items
        assert len(arts) == 2
        assert arts[0].type == "article"
        assert arts[0].title == ARTICLE3
        assert arts[0].displaytitle == "Display Title 1"
        assert arts[1].title == "Article 4"
        assert arts[1].revision == "4"
        assert arts[1].displaytitle == "Display Title 2"

    # first parse_string
    mb = metabook.parse_collection_page(test_wikitext1)
    print(mb)

    assert mb.type == "collection"
    assert mb.version == 1
    assert mb.title == "Title"
    assert mb.subtitle == "Subtitle"
    assert mb.summary == "Summary line 1 Summary line 2 "
    verify_items(mb.items)

    # second parse_string
    mb = metabook.parse_collection_page(test_wikitext2)
    assert mb.type == "collection"
    assert mb.version == metabook.collection.version
    assert mb.title == "Title"
    assert mb.subtitle == "Subtitle"
    assert mb.summary == "Summary line 1 Summary line 2 "
    verify_items(mb.items)


def test_get_item_list():
    expected = [
        {
            "type": "Chapter",
            "title": CHAPTER1,
        },
        {
            "type": "article",
            "title": ARTICLE1,
        },
        {
            "type": "article",
            "title": ARTICLE2,
        },
        {
            "type": "Chapter",
            "title": CHAPTER2,
        },
        {
            "type": "article",
            "title": ARTICLE3,
        },
    ]

    result = test_metabook.walk()
    assert len(result) == len(expected)
    for e, r in zip(expected, result, strict=False):
        assert e["type"] == r.type
        assert e["title"] == r.title

    expected = [
        {
            "type": "article",
            "title": ARTICLE1,
        },
        {
            "type": "article",
            "title": ARTICLE2,
        },
        {
            "type": "article",
            "title": ARTICLE3,
        },
    ]
    result = test_metabook.walk(filter_type="article")
    assert len(result) == len(expected)
    for e, r in zip(expected, result, strict=False):
        assert e["type"] == r.type
        assert e["title"] == r.title


def test_checksum():
    cs1 = metabook.calc_checksum(test_metabook)
    print(cs1)
    assert cs1
    assert isinstance(cs1, str)
    import copy

    tm2 = copy.deepcopy(test_metabook)

    tm2.title = tm2.title + "123"
    assert metabook.calc_checksum(tm2) != cs1
