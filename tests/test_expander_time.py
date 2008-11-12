#! /usr/bin/env py.test

from mwlib import expander
from mwlib.expander import expandstr, DictDB
from mwlib.xfail import xfail

def et(s, expected):
    expandstr(u'{{#time:%s' % (s,), expected)
    
    
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

    yield e, "N", "7", "2008-11-9" # sunday
    yield e, "N", "1", "2008-11-10"

    
    yield e, "w", "0", "2008-11-9" # sunday
    yield e, "w", "1", "2008-11-10"


    yield e, "a", "am"
    yield e, "a", "pm", "09 Feb 2008 12:00:00"
    
    yield e, "A", "AM"
    yield e, "A", "PM", "09 Feb 2008 12:00:00"
    
    
