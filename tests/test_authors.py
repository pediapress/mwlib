#! /usr/bin/env py.test
from mwlib import authors

example_1 = [
    {
        "comment": "Dated {{Dead link}}. (Build p607)",
        "minor": "",
        "parentid": 417308957,
        "revid": 417310285,
        "size": 925,
        "user": "SmackBot",
    },
    {
        "comment": "{{dead link}}",
        "parentid": 397347170,
        "revid": 417308957,
        "size": 909,
        "user": "Denelson83",
    },
    {
        "comment": "",
        "parentid": 304555476,
        "revid": 397347170,
        "size": 896,
        "user": "Palaeozoic99",
    },
    {
        "comment": "narrower cat",
        "parentid": 228403955,
        "revid": 304555476,
        "size": 880,
        "user": "The Tom",
    },
    {
        "comment": "remove line",
        "minor": "",
        "parentid": 222909353,
        "revid": 228403955,
        "size": 878,
        "user": "Kwanesum",
    },
    {"comment": "", "parentid": 222907785, "revid": 222909353, "size": 884, "user": "Skookum1"},
    {
        "comment": "stub sort",
        "parentid": 192472026,
        "revid": 222907785,
        "size": 884,
        "user": "Skookum1",
    },
    {"comment": "add category", "revid": 192472026, "size": 850, "user": "CosmicPenguin"},
    {
        "comment": "migrate coor to {{[[Template:Coord|coord]]}}, add name parameter  using [[Project:AutoWikiBrowser|AWB]]",
        "minor": "",
        "revid": 189340607,
        "size": 807,
        "user": "Qyd",
    },
    {
        "comment": "removing extra ]",
        "minor": "",
        "parentid": 100254749,
        "revid": 100254810,
        "size": 783,
        "user": "Nationalparks",
    },
    {
        "comment": "expanded with link",
        "parentid": 75720259,
        "revid": 100254749,
        "size": 784,
        "user": "Nationalparks",
    },
    {
        "comment": "coor, links",
        "parentid": 47218945,
        "revid": 75720259,
        "size": 583,
        "user": "Qyd",
    },
    {
        "comment": "info, cat",
        "minor": "",
        "parentid": 47218755,
        "revid": 47218945,
        "size": 457,
        "user": "Nationalparks",
    },
    {
        "comment": "new stub",
        "parentid": 0,
        "revid": 47218755,
        "size": 362,
        "user": "Nationalparks",
    },
]


def test_empty():
    assert authors.get_authors([]) == []


def test_example_1():
    a = authors.get_authors(example_1)
    print(a)
    assert a == [
        "CosmicPenguin",
        "Denelson83",
        "Kwanesum",
        "Nationalparks",
        "Palaeozoic99",
        "Qyd",
        "Skookum1",
        "The Tom",
        "ANONIPEDITS:0",
    ]
