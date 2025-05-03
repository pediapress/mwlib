#! /usr/bin/env py.test
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.
from mwlib.parser.advtree import (
    Article,
    Cell,
    ImageLink,
    PreFormatted,
    Row,
    Section,
    Strong,
    Table,
    Text,
    build_advanced_tree,
)
from mwlib.utils.sanitychecker import (
    Allow,
    ChildrenOf,
    Equal,
    Forbid,
    Require,
    RequireChild,
    SanityChecker,
    SanityException,
    removecb,
)


def setup():
    # WARNING, ALTERING THIS'll PROPABLY BREAK ALL TESTS! EDIT WITH CARE
    t = [
        Article(),
        [Section(), [PreFormatted(), [Text("bla blub"), ImageLink()]]],
        [Table(), [Row(), [Cell(), PreFormatted(), [Text("jo")]], ImageLink()]],
        [Section(), [Section(), [Strong()]]],
        [Text("bla")],
    ]
    # WARNING, ALTERING THE ABOVE PROPABLY BREAK ALL TESTS! EDIT WITH CARE

    def rec(elements, parent):
        last = None
        for c in elements:
            if isinstance(c, type([])):
                assert last
                rec(c, last)
            else:
                if parent:
                    parent.children.append(c)
                last = c

    rec(t, None)
    t = t[0]
    build_advanced_tree(t)

    return t


def checkpass(*rules):
    tree = setup()
    sc = SanityChecker()
    for r in rules:
        sc.add_rule(r)
    sc.check(tree)  # should pass


def checkfail(*rules):
    tree = setup()
    sc = SanityChecker()
    for r in rules:
        sc.add_rule(r)
    failed = False
    try:
        sc.check(tree)
    except SanityException:
        failed = True
    assert failed


def test_allow():
    checkfail(ChildrenOf(Table, Allow(Row)))
    checkpass(ChildrenOf(Article, Allow(Section, Text, Table)))


def test_require():
    checkfail(ChildrenOf(PreFormatted, Require(Section)))
    checkpass(ChildrenOf(PreFormatted, Require(Text)))


def test_forbid():
    checkfail(ChildrenOf(Section, Forbid(Section)))
    checkpass(ChildrenOf(Table, Forbid(Section)))


def test_equal():
    checkfail(ChildrenOf(Table, Equal(Row, Row)))
    checkpass(ChildrenOf(Article, Equal(Section, Table, Section, Text)))


def test_remove_cb():
    checkfail(RequireChild(Strong))
    tree = setup()
    sc = SanityChecker()
    sc.add_rule(RequireChild(Strong), removecb)  # this removes the
    sc.check(tree)
    # now traverse this tree and assert there is no strong
    for c in tree.allchildren():
        assert not isinstance(c, Strong)
