#! /usr/bin/env python

# taken from http://code.activestate.com/recipes/306860/ by Andrew Dalke

# Format a datetime through its full proleptic Gregorian date range.
#
# >>> strftime(datetime.date(1850, 8, 2), "%Y/%M/%d was a %A")
# '1850/00/02 was a Friday'
# >>>


import datetime
import re
import time

# remove the unsupposed "%s" command.  But don't
# do it if there's an even number of %s before the s
# because those are all escaped.  Can't simply
# remove the s because the result of
#  %sY
# should be %Y if %s isn't supported, not the
# 4 digit year.
_illegal_s = re.compile(r"((^|[^%])(%%)*%s)")


def _findall(text, substr):
    # Also finds overlaps
    sites = []
    i = 0
    while True:
        j = text.find(substr, i)
        if j == -1:
            break
        sites.append(j)
        i = j + 1
    return sites


# Every 28 years the calendar repeats, except through century leap
# years where it's 6 years.  But only if you're using the Gregorian
# calendar.  ;)


def strftime(date, fmt):
    if _illegal_s.search(fmt):
        raise TypeError("This strftime implementation does not handle %s")
    if date.year > 1900:
        return date.strftime(fmt)

    year = date.year
    # For every non-leap year century, advance by
    # 6 years to get into the 28-year repeat cycle
    delta = 2000 - year
    off = 6 * (delta // 100 + delta // 400)
    year = year + off

    # Move to around the year 2000
    year = year + ((2000 - year) // 28) * 28
    timetuple = date.timetuple()
    time_1 = time.strftime(fmt, (year,) + timetuple[1:])
    sites1 = _findall(time_1, str(year))

    time_2 = time.strftime(fmt, (year + 28,) + timetuple[1:])
    sites2 = _findall(time_2, str(year + 28))

    sites = []
    for site in sites1:
        if site in sites2:
            sites.append(site)

    result_time = time_1
    syear = f"{date.year}"
    for site in sites:
        result_time = result_time[:site] + syear + result_time[site + 4 :]
    return result_time


# Make sure that the day names are in order
# from 1/1/1 until August 2000


def test():
    formatted_year_comparison = strftime(datetime.date(1800, 9, 23), "%Y has the same days as 1980 and 2008")
    if formatted_year_comparison != "1800 has the same days as 1980 and 2008":
        raise AssertionError(formatted_year_comparison)

    print("Testing all day names from 0001/01/01 until 2000/08/01")
    # Get the weekdays.  Can't hard code them; they could be
    # localized.
    days = []
    for i in range(1, 10):
        days.append(datetime.date(2000, 1, i).strftime("%A"))
    nextday = {}
    for i in range(8):
        nextday[days[i]] = days[i + 1]

    startdate = datetime.date(1, 1, 1)
    enddate = datetime.date(2000, 8, 1)
    prevday = strftime(startdate, "%A")
    one_day = datetime.timedelta(1)

    testdate = startdate + one_day
    while testdate < enddate:
        if testdate.day == 1 and testdate.month == 1 and (testdate.year % 100 == 0):
            print("Testing century", testdate.year)
        day = strftime(testdate, "%A")
        if nextday[prevday] != day:
            raise AssertionError(str(testdate))
        prevday = day
        testdate = testdate + one_day


if __name__ == "__main__":
    test()
