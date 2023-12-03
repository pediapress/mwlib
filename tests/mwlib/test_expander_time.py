#! /usr/bin/env py.test
import pytest
from mwlib.templ.misc import expand_str

cases = [
    ("Y-m-d", "2008-02-09"),
    ("Y", "2008"),
    ("y", "08"),
    ("n", "2"),
    ("m", "02"),
    ("M", "Feb"),
    ("F", "February"),
    ("W", "06"),
    ("j", "9"),
    ("d", "09"),
    ("z", "39"),
    ("D", "Sat"),
    ("l", "Saturday"),
    ("N", "7", "2008-11-9"),
    ("N", "1", "2008-11-10"),  # sunday,
    ("w", "0", "2008-11-9"),
    ("w", "1", "2008-11-10"),  # sunday,
    ("a", "am"),
    ("a", "pm", "09 Feb 2008 12:00:00"),
    ("A", "AM"),
    ("A", "PM", "09 Feb 2008 12:00:00"),
    ("g", "10"),
    ("g", "12", "09 Feb 2008 12:00:00"),
    ("g", "1", "09 Feb 2008 13:00:00"),
    ("g", "12", "09 Feb 2008 00:00:00"),
    ("h", "10"),
    ("h", "12", "09 Feb 2008 12:00:00"),
    ("h", "01", "09 Feb 2008 13:00:00"),
    ("g", "12", "09 Feb 2008 00:00:00"),
    ("G", "1", "09 Feb 2008 01:00:00"),
    ("G", "23", "09 Feb 2008 23:00:00"),
    ("H", "01", "09 Feb 2008 01:00:00"),
    ("H", "23", "09 Feb 2008 23:00:00"),
    ("i", "55"),
    ("s", "17"),
    ("U", "1202554517"),
    ("L", "1"),
    ("L", "1", "09 Feb 2000"),
    ("L", "0", "09 Feb 2009"),
    ("t", "29"),
    ("c", "2008-02-09T10:55:17+00:00"),
    ("r", "Sat, 09 Feb 2008 10:55:17 +0000"),
    ("xrY", "MMVIII"),
    ("xrU", "XVI", "1970-1-1 + 16 second"),
    ('xr"foobar"', "foobar"),
]


@pytest.mark.parametrize("case", cases)
def test_codes(case):
    date = "09 Feb 2008 10:55:17"
    if len(case) == 3:
        date = case[2]
    expand_str(f"{{{{#time:{case[0]}|{date}}}}}", case[1])


def test_examples():
    expand_str(
        '{{ #time: l [[F j|"Fourth of" F]] [[Y]] | 4 March 2007 }}',
        "Sunday [[March 4|Fourth of March]] [[2007]]",
    )


def test_backslash_quote():
    expand_str("{{#time: \\Y|4 March 2007}}", "Y")
    expand_str("{{#time: \\\\Y|4 March 2007}}", "\\2007")


def test_time_vs_year():
    """http://code.pediapress.com/wiki/ticket/350"""
    expand_str("{{#time:G:i|2008}}", "20:08")


def test_time_vs_year_illegal_time():
    expand_str("{{#time:Y|1970}}", "1970")


def test_before_1900():
    expand_str("{{#time:c|1883-1-1}}", "1883-01-01T00:00:00+00:00")


def test_dateutil_raises_typeerror():
    expand_str("{{#time:c|2007-09-27PM EDT}}")
    expand_str("{{#iferror:{{#time:c|2007-09-27PM EDT}}|yes|no}}", "yes")


def test_time_minus_days():
    expand_str("{{#time:Y-m-d| 20070827000000 -12 day}}", "2007-08-15")
