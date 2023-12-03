#! /usr/bin/env py.test

import pytest

from qs import qserve


def defopts(**kw):
    res = {"interface": "0.0.0.0", "data_dir": None, "allowed_ips": set([]), "port": 14311}
    res.update(kw)
    return res


@pytest.fixture
def main(request):
    return qserve.Main(0, "0.0.0.0", None, allowed_ips=set())


# -- tests


def test_port_from_str():
    p = qserve.port_from_str
    pytest.raises(ValueError, p, "1.0")
    pytest.raises(ValueError, p, "-1")
    pytest.raises(ValueError, p, "65536")
    assert p("0") == 0
    assert p("1") == 1
    assert p("65535") == 65535


def test_usage():
    qserve.usage()


def test_is_allowed_ip(main):
    a = main.is_allowed_ip
    assert a("127.0.0.1")

    main.allowed_ips.add("192.168.10.210")
    assert not a("127.0.0.1")
    assert a("192.168.10.210")


def test_parse_options_default():
    options = qserve.parse_options([])
    assert options == defopts()


def test_parse_options_port():
    options = qserve.parse_options(["-p", "8000"])
    assert options == defopts(port=8000)

    options = qserve.parse_options(["--port", "8000"])
    assert options == defopts(port=8000)


def test_parse_options_interface():
    options = qserve.parse_options(["-i", "127.0.0.1"])
    assert options == defopts(interface="127.0.0.1")

    options = qserve.parse_options(["--interface", "127.0.0.1"])
    assert options == defopts(interface="127.0.0.1")


def test_parse_options_data_dir():
    options = qserve.parse_options(["-d", "/tmp/foo"])
    assert options == defopts(data_dir="/tmp/foo")


def test_parse_options_allowed_ip():
    options = qserve.parse_options(["-a", "127.0.0.1", "-a", "192.168.10.210"])
    assert options == defopts(allowed_ips={"127.0.0.1", "192.168.10.210"})


def test_parse_options_help():
    pytest.raises(SystemExit, qserve.parse_options, ["-h"])
    pytest.raises(SystemExit, qserve.parse_options, ["--help"])


def test_parse_options_too_many_arguments():
    pytest.raises(SystemExit, qserve.parse_options, ["foobar"])
