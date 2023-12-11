#! /usr/bin/env py.test
from mwlib.expander import parse
from mwlib.siteinfo import get_siteinfo
from mwlib.templ import magic_nodes, nodes

nl_siteinfo = get_siteinfo("nl")


def test_no_arguments():
    t = parse("{{bla}}")
    assert t[1] == (), "expected an empty tuple"


def test_one_empty_arguments():
    t = parse("{{bla|}}")
    assert len(t[1]) == 1, "expected exactly one argument"


def test_parse_if():
    t = parse("{{#if: 1 | yes | no}}")
    print(t)
    assert isinstance(t, nodes.IfNode)

    t = parse("{{#if: 1 | yes | no}}", siteinfo=nl_siteinfo)
    print(t)
    assert isinstance(t, nodes.IfNode)


def test_parse_if_localized():
    t = parse("{{#als: 1 | yes | no}}", siteinfo=nl_siteinfo)
    print(t)
    assert isinstance(t, nodes.IfNode)


def test_parse_switch():
    t = parse("{{#switch: A | a=lower | UPPER}}")
    print(t)
    assert isinstance(t, nodes.SwitchNode)

    t = parse("{{#switch: A | a=lower | UPPER}}", siteinfo=nl_siteinfo)
    print(t)
    assert isinstance(t, nodes.SwitchNode)


def test_parse_switch_localized():
    t = parse("{{#schakelen: A | a=lower | UPPER}}", siteinfo=nl_siteinfo)
    print(t)
    assert isinstance(t, nodes.SwitchNode)


def test_parse_time():
    t = parse("{{#time:Y-m-d|2006-09-28}}")
    print(t)
    assert isinstance(t, magic_nodes.Time)


def test_parse_time_localized():
    t = parse("{{#tijd:Y-m-d|2006-09-28}}", siteinfo=nl_siteinfo)
    print(t)
    assert isinstance(t, magic_nodes.Time)
