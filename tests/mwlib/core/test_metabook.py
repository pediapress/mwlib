#! /usr/bin/env py.test
import copy

import pytest

from mwlib.core import metabook
from mwlib.utils import myjson

ARTICLE1 = "Lame Article 1"
ARTICLE2 = "Dull Article 2"
ARTICLE3 = "Nice Article 3"
CHAPTER1 = "Foo Chapter 1"
CHAPTER2 = "Bar Chapter 2"
TEXT_X_WIKI = "text/x-wiki"

test_wikitext1 = f"""== Title ==
=== Subtitle ===
{{{{Template}}}}

Summary line 1
Summary line 2

;{CHAPTER1}
:[[{ARTICLE1}]]
:[[:{ARTICLE2}]]

;{CHAPTER2}
:[[{ARTICLE3}|Display Title 1]]
:[{{{{fullurl:Article 4|oldid=4}}}}Display Title 2]

"""

test_wikitext2 = """== Title ==
=== Subtitle ===
{{
Template
}}

Summary line 1
Summary line 2

;Foo Chapter 1
:[[Lame Article 1]]
:[[:Dull Article 2]]

;Bar Chapter 2
:[[Nice Article 3|Display Title 1]]
:[{{fullurl:Article 4|oldid=4}}Display Title 2]

"""

metabook1 = {
    "type": "Collection",
    "version": 1,
    "title": "bla",
    "items": [
        {
            "type": "Chapter",
            "title": CHAPTER1,
            "items": [
                {
                    "type": "Article",
                    "title": ARTICLE1,
                    "content_type": TEXT_X_WIKI,
                },
                {
                    "type": "Article",
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
                    "type": "Article",
                    "title": ARTICLE3,
                    "displaytitle": "Display Title",
                    "content_type": TEXT_X_WIKI,
                },
            ],
        },
    ],
}


# Create a copy of the original dictionary
metabook2 = copy.deepcopy(metabook1)

# Modify the top-level "type" key
metabook2["type"] = metabook2["type"].lower()

# Modify "type" keys in first-level items (chapters)
for i in range(len(metabook2["items"])):
    metabook2["items"][i] = metabook2["items"][i].copy()
    metabook2["items"][i]["type"] = metabook2["items"][i]["type"].lower()

    # Modify "type" keys in second-level items (articles)
    for j in range(len(metabook2["items"][i]["items"])):
        metabook2["items"][i]["items"][j] = metabook2["items"][i]["items"][j].copy()
        metabook2["items"][i]["items"][j]["type"] = metabook2["items"][i]["items"][j][
            "type"
        ].lower()

metabook1 = myjson.loads(myjson.dumps(metabook1))
metabook2 = myjson.loads(myjson.dumps(metabook2))


def test_parse_collection_page():
    def verify_items(items):
        assert len(items) == 2
        assert items[0].type == "Chapter"
        assert items[0].title == CHAPTER1
        arts = items[0].items
        assert len(arts) == 2
        assert arts[0].type == "Article"
        assert arts[0].title == ARTICLE1
        assert arts[1].type == "Article"
        assert arts[1].title == ARTICLE2
        assert items[1].type == "Chapter"
        assert items[1].title == CHAPTER2
        arts = items[1].items
        assert len(arts) == 2
        assert arts[0].type == "Article"
        assert arts[0].title == ARTICLE3
        assert arts[0].displaytitle == "Display Title 1"
        assert arts[1].title == "Article 4"
        assert arts[1].revision == "4"
        assert arts[1].displaytitle == "Display Title 2"

    # first parse_string
    mb = metabook.parse_collection_page(test_wikitext1)
    print(mb)

    assert mb.type == "Collection"
    assert mb.version == 1
    assert mb.title == "Title"
    assert mb.subtitle == "Subtitle"
    assert mb.summary == "Summary line 1 Summary line 2 "
    verify_items(mb.items)

    # second parse_string
    mb = metabook.parse_collection_page(test_wikitext2)
    assert mb.type == "Collection"
    assert mb.version == metabook.Collection.version
    assert mb.title == "Title"
    assert mb.subtitle == "Subtitle"
    assert mb.summary == "Summary line 1 Summary line 2 "
    verify_items(mb.items)


@pytest.mark.parametrize("test_metabook", [metabook1, metabook2])
def test_get_item_list(test_metabook):
    expected = [
        {"type": "Chapter", "title": CHAPTER1 },
        {"type": "Article", "title": ARTICLE1 },
        {"type": "Article", "title": ARTICLE2 },
        {"type": "Chapter", "title": CHAPTER2 },
        {"type": "Article", "title": ARTICLE3 },
    ]

    result = test_metabook.walk()
    assert len(result) == len(expected)
    for e, r in zip(expected, result, strict=False):
        assert e["type"] == r.type
        assert e["title"] == r.title

    expected = [
        {"type": "Article", "title": ARTICLE1 },
        {"type": "Article", "title": ARTICLE2 },
        {"type": "Article", "title": ARTICLE3 },
    ]
    result = test_metabook.walk(filter_type="Article")
    assert len(result) == len(expected)
    for e, r in zip(expected, result, strict=False):
        assert e["type"] == r.type
        assert e["title"] == r.title


def test_metabook_append_articles():
    mb = metabook.Collection()
    mb.append_article("Monty Python")
    mb_json = mb._json()
    assert isinstance(mb_json, dict)
    assert len(mb.get_articles()) == 1
    for article in mb.get_articles():
        assert article.title == "Monty Python"
        assert isinstance(article, metabook.Article)


def test_checksum():
    cs1 = metabook.calc_checksum(metabook1)
    print(cs1)
    assert cs1
    assert isinstance(cs1, str)

    tm2 = copy.deepcopy(metabook1)

    tm2.title = tm2.title + "123"
    assert metabook.calc_checksum(tm2) != cs1


def test_get_wiki():
    """Test the collection.get_wiki() method."""
    # Create a collection with wikis
    coll = metabook.Collection()

    # Create WikiConf objects with different ident and baseurl values
    wiki1 = metabook.WikiConf(ident="wiki1", baseurl="http://wiki1.example.org")
    wiki2 = metabook.WikiConf(ident="wiki2", baseurl="http://wiki2.example.org")

    # Add wikis to the collection
    coll.wikis = [wiki1, wiki2]

    # Test finding a wiki by ident
    found_wiki = coll.get_wiki(ident="wiki1")
    assert found_wiki is wiki1

    # Test finding a wiki by baseurl
    found_wiki = coll.get_wiki(baseurl="http://wiki2.example.org")
    assert found_wiki is wiki2

    # Test not finding a wiki
    found_wiki = coll.get_wiki(ident="nonexistent")
    assert found_wiki is None

    found_wiki = coll.get_wiki(baseurl="http://nonexistent.example.org")
    assert found_wiki is None

    # Test providing both ident and baseurl (should raise ValueError)
    with pytest.raises(ValueError):
        coll.get_wiki(ident="wiki1", baseurl="http://wiki1.example.org")

    # Test providing neither ident nor baseurl (should raise ValueError)
    with pytest.raises(ValueError):
        coll.get_wiki()
