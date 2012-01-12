#! /usr/bin/env py.test

from mwlib.expander import expandstr
from mwlib.xfail import xfail


def test_codes():
    def e(s, expected, date="09 Feb 2008 10:55:17"):
        expandstr(u'{{#time:%s|%s}}' % (s, date), expected)

    yield e, "Y-m-d", "2008-02-09"

    yield e, "Y", "2008"
    yield e, "y", "08"

    yield e, "n", "2"
    yield e, "m", "02"
    yield e, "M", "Feb"
    yield e, "F", "February"
    yield e, "W", "06"
    yield e, "j", "9"
    yield e, "d", "09"
    yield e, "z", "39"
    yield e, "D", "Sat"

    yield e, "l", "Saturday"

    yield e, "N", "7", "2008-11-9"  # sunday
    yield e, "N", "1", "2008-11-10"

    yield e, "w", "0", "2008-11-9"  # sunday
    yield e, "w", "1", "2008-11-10"

    yield e, "a", "am"
    yield e, "a", "pm", "09 Feb 2008 12:00:00"

    yield e, "A", "AM"
    yield e, "A", "PM", "09 Feb 2008 12:00:00"

    yield e, "g", "10"
    yield e, "g", "12", "09 Feb 2008 12:00:00"
    yield e, "g", "1", "09 Feb 2008 13:00:00"
    yield e, "g", "12", "09 Feb 2008 00:00:00"

    yield e, "h", "10"
    yield e, "h", "12", "09 Feb 2008 12:00:00"
    yield e, "h", "01", "09 Feb 2008 13:00:00"
    yield e, "g", "12", "09 Feb 2008 00:00:00"

    yield e, "G", "1", "09 Feb 2008 01:00:00"
    yield e, "G", "23", "09 Feb 2008 23:00:00"

    yield e, "H", "01", "09 Feb 2008 01:00:00"
    yield e, "H", "23", "09 Feb 2008 23:00:00"

    yield e, "i", "55"
    yield e, "s", "17"

    yield e, "U", "1202554517"

    yield e, "L", "1"
    yield e, "L", "1", "09 Feb 2000"
    yield e, "L", "0", "09 Feb 2009"

    yield e, "t", "29"

    yield e, "c", "2008-02-09T10:55:17+00:00"

    yield e, "r", "Sat, 09 Feb 2008 10:55:17 +0000"

    yield e, "xrY", "MMVIII"
    yield e, "xrU", "XVI", "1970-1-1 + 16 second"
    yield e, 'xr"foobar"', "foobar"


def test_examples():
    yield expandstr, '{{ #time: l [[F j|"Fourth of" F]] [[Y]] | 4 March 2007 }}', 'Sunday [[March 4|Fourth of March]] [[2007]]'


def test_backslash_quote():
    yield expandstr, '{{#time: \\Y|4 March 2007}}', 'Y'
    yield expandstr, '{{#time: \\\\Y|4 March 2007}}', '\\2007'


def test_time_vs_year():
    """http://code.pediapress.com/wiki/ticket/350"""
    expandstr('{{#time:G:i|2008}}', '20:08')


def test_time_vs_year_illegal_time():
    expandstr('{{#time:Y|1970}}', "1970")


def test_before_1900():
    expandstr("{{#time:c|1883-1-1}}", "1883-01-01T00:00:00+00:00")


def test_dateutil_raises_typeerror():
    yield expandstr, "{{#time:c|2007-09-27PM EDT}}"
    yield expandstr, "{{#iferror:{{#time:c|2007-09-27PM EDT}}|yes|no}}", "yes"


def test_time_minus_days():
    yield expandstr, "{{#time:Y-m-d| 20070827000000 -12 day}}", "2007-08-15"
