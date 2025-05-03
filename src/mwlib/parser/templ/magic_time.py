import calendar
import datetime
import re
import sys
from contextlib import suppress

import roman
from timelib import strtodatetime as parsedate

from mwlib.utils.strftime import strftime


def ampm(date):
    if date.hour < 12:
        return "am"
    else:
        return "pm"


COMPILED_REGEX = re.compile('"[^"]*"|xr|\\\\.|.')
CODENAMES = {
    "y": "%y",
    "Y": "%Y",
    "n": lambda d: str(d.month),
    "m": "%m",
    "M": "%b",
    "F": "%B",
    "W": lambda d: "%02d" % (d.isocalendar()[1],),
    "j": lambda d: str(d.day),
    "d": "%d",
    "z": lambda d: str(d.timetuple().tm_yday - 1),
    "D": "%a",
    "l": "%A",
    "N": lambda d: str(d.isoweekday()),
    "w": lambda d: str(d.isoweekday() % 7),
    "a": lambda d: d.strftime("%p").lower(),
    "A": lambda d: d.strftime("%p"),
    "g": lambda d: str(((d.hour - 1) % 12) + 1),
    "h": "%I",
    "G": lambda d: str(d.hour),
    "H": lambda d: "%02d" % (d.hour,),
    "i": "%M",
    "s": "%S",
    "U": lambda d: str(calendar.timegm(d.timetuple())),
    "L": lambda d: str(int(calendar.isleap(d.year))),
    "c": "%Y-%m-%dT%H:%M:%S+00:00",
    "r": "%a, %d %b %Y %H:%M:%S +0000",
    "t": lambda d: str(calendar.monthrange(d.year, d.month)[1]),
    "xr": ("process_next", lambda n: roman.toRoman(int(n))),
}


def _format_and_process_date(format_code, date, tmp, process_next):
    if isinstance(format_code, tuple):
        process_next = format_code[1]
        return process_next
    res = (
        strftime(date, format_code)
        if isinstance(format_code, str)
        else format_code(date)
    )
    if process_next:
        with suppress(ValueError):
            res = process_next(res)
        process_next = None
    tmp.append(res)
    return process_next


def format_date(format_str, date):
    split = COMPILED_REGEX.findall(format_str)
    process_next = None

    tmp = []
    for element in split:
        format_code = CODENAMES.get(element)
        if format_code is None:
            if len(element) == 2 and element.startswith("\\"):
                tmp.append(element[1])
            elif len(element) >= 2 and element.startswith('"'):
                tmp.append(element[1:-1])
            else:
                tmp.append(element)
        else:
            process_next = _format_and_process_date(format_code, date, tmp, process_next)


    tmp = "".join(tmp).strip()
    return tmp


def _parse_date_string(date, date_string):
    if isinstance(date_string, str):
        # transform to bytes
        date_string = date_string.encode("utf-8")
    try:
        date = parsedate(date_string)
    except ValueError:
        pass
    except Exception as err:
        sys.stderr.write(
            f"ERROR in parsedate: {err!r} while parsing {date_string!r}"
        )
    return date


def time(date_format, date_string=None):
    date = None
    if date_string:
        if re.match(r"\d\d\d\d$", date_string):
            with suppress(ValueError):
                date = datetime.datetime.now().replace(
                    hour=int(date_string[:2]), minute=int(date_string[2:]), second=0
                )

        if date is None:
            date = _parse_date_string(date, date_string)

        if date is None:
            return '<strong class="error">Error: invalid time</strong>'

    if date is None:
        date = datetime.datetime.now()

    return format_date(date_format, date)
