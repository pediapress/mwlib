#! /usr/bin/env py.test
# -*- coding: utf-8 -*-

"""tests for the convert macros, I can't get them to work inside our
mediawiki installation.
"""


from mwlib import expander
from mwlib.expander import expandstr, DictDB

db = {
"convert":
"""<includeonly>{{convert/{{{2}}}|{{{1}}}|{{#ifeq:{{#expr:{{{3|0}}}*0}}|0|0}}|{{{3|}}}|{{{4|}}}|{{{5|}}}|{{{6|}}}|r={{#ifeq:{{{sp}}}|us|er|re}}|d=L{{{lk|off}}}A{{{abbr|off}}}D{{{disp|b}}}S{{{adj|{{{sing|off}}}}}}|s={{{sigfig|}}}}}</includeonly><noinclude>{{pp-template|small=yes}}{{esoteric}}
{{template doc}}</noinclude>""",

"convert/ft":
"""{{convert/{{#ifeq:{{{4}}}|in|and/in|{{{d}}}}}|{{{1}}}|{{{2|}}}|{{{3|}}}|{{{4|}}}|{{{5|}}}|{{{6|}}}|s={{{s|}}}|r={{{r}}}|d={{{d}}}
|u=ft
|n=foot
|l=feet
|t=Foot (length)
|o=m
|b=0.3048
|j=-0.515985037-{{{j|0}}}}}<noinclude>{{pp-template|small=yes}}
[[Category:Subtemplates of Template Convert]]
</noinclude>
""",

"Convert/LoffAoffDbSoff":
"""{{formatnum:{{{1}}}}}&nbsp;{{#ifeq:{{{1}}}|1|{{{n}}}|{{{l|{{{n}}}s}}}}} ({{convert/{{#if:{{{2|}}}|{{{o}}}|{{{3}}}}}|{{{1}}}|{{{1}}}*{{{b}}}|{{#if:{{{2|}}}|{{{3|}}}|{{{4|}}}}}|{{{s|}}}|r={{{r}}}|j={{{j}}}|d=LoffAonSoff}})<noinclude>
[[Category:Subtemplates of Template Convert]]{{pp-template|small=yes}}
</noinclude>""",
"convert/m":
"""{{convert/{{{d}}}|{{{1}}}|{{{2|}}}|{{{3|}}}|{{{4|}}}|s={{{s|}}}|r={{{r}}}
|u=m
|n=met{{{r}}}
|t=metre
|o=ft
|b=1
|j=0-{{{j|0}}}}}<noinclude>{{pp-template|small=yes}}
[[Category:Subtemplates of Template Convert]]
</noinclude>""",

"Convert/LoffAonSoff":
"""{{convert/{{#if:{{{4|}}}|s}}{{#if:{{{3|}}}|p}}round|{{{1}}}|{{{2}}}/{{{b}}}|{{{3}}}|{{{4}}}|{{{j}}}}}&nbsp;{{{u}}}<noinclude>
[[Category:Subtemplates of Template Convert]]{{pp-template|small=yes}}
</noinclude>""",

"Convert/round":
"""{{#ifexpr:{{{2}}}=0|0|{{formatnum:{{rnd|{{{2}}}|({{max/2|{{precision/+|1{{{1}}}}}+({{{5}}}-0.1989700043)round0|1-{{ordomag|{{{2}}}}}}})}}}}}}<noinclude>
[[Category:Subtemplates of Template Convert]]{{pp-template|small=yes}}
</noinclude>""",

"Rnd":
"""<includeonly>{{rnd/+|{{{1}}}|{{{2}}}|{{rnd/0{{#expr:{{{2}}}>0}}|{{{1}}}|{{{2}}}}}}}</includeonly><noinclude>{{pp-template}}
{{template doc}}
</noinclude>""",

"Rnd/+":
"""<includeonly>{{#ifeq:{{#expr:{{{3}}}*0}}|0|{{{3}}}|{{#expr:{{{1}}}round{{{2}}}}}}}</includeonly><noinclude>{{pp-template|small=yes}}</noinclude>""",

"Max/2":
"""<includeonly>{{#ifexpr:{{{1}}}<{{{2}}}|{{{2}}}|{{{1}}}}}</includeonly><noinclude>
{{pp-template|small=yes}}2-parameter version</noinclude>""",

"Precision/+":
"""<includeonly>{{#expr:{{precision/{{#expr:3*{{{1}}}>{{{1}}}0}}|{{{1}}}}}}}</includeonly><noinclude>
{{pp-template|small=yes}}</noinclude>""",

"Precision/0":
"""<includeonly>{{precision/0{{#expr:{{{1}}}={{{1}}}round-6}}|1{{{1}}}}}</includeonly><noinclude>
{{pp-template|small=yes}}</noinclude>""",

"Precision/00":
"""<includeonly>-({{{1}}}={{{1}}}round-5)-({{{1}}}={{{1}}}round-4)-({{{1}}}={{{1}}}round-3)-({{{1}}}={{{1}}}round-2)-({{{1}}}={{{1}}}round-1)</includeonly><noinclude>
{{pp-template|small=yes}}</noinclude>""",
"Ordomag":
"""{{Ordomag/+|{{#ifexpr:{{{1}}}<0|-}}{{{1}}}}}<noinclude>{{pp-template|small=yes}}{{documentation}}</noinclude>""",

"Ordomag/+":
"""<includeonly>{{#expr:{{Ordomag/{{#expr:({{{1}}}>=1000000)-(1>{{{1}}})}}|{{{1}}}}}}}</includeonly><noinclude>
{{pp-template|small=yes}}</noinclude>""",

"Ordomag/-1":
"""{{ordomag/{{#expr:0-2*({{{1}}}<0.000001)}}|{{{1}}}*1000000}}-6""",

"Ordomag/0":
"""<includeonly>5-({{{1}}}<100000)-({{{1}}}<10000)-({{{1}}}<1000)-({{{1}}}<100)-({{{1}}}<10)</includeonly><noinclude>
{{pp-template|small=yes}}</noinclude>""",

"Rnd/01":
"""{{rnd/-|{{#expr:{{{1}}}round{{{2}}}}}|{{{2}}}}}<noinclude>{{pp-template}}</noinclude>""",

"Rnd/-":
"""<includeonly>{{#expr:{{{1}}}}}<!--
-->{{#ifexpr: {{{2}}}>0  and {{{1}}}={{{1}}}round0 |.0}}<!--
-->{{#ifexpr: {{{2}}}>1  and {{{1}}}={{{1}}}round1  |0}}<!--
-->{{#ifexpr: {{{2}}}>2  and {{{1}}}={{{1}}}round2  |0}}<!--
-->{{#ifexpr: {{{2}}}>3  and {{{1}}}={{{1}}}round3  |0}}<!--
-->{{#ifexpr: {{{2}}}>4  and {{{1}}}={{{1}}}round4  |0}}<!--
-->{{#ifexpr: {{{2}}}>5  and {{{1}}}={{{1}}}round5  |0}}<!--
-->{{#ifexpr: {{{2}}}>6  and {{{1}}}={{{1}}}round6  |0}}<!--
-->{{#ifexpr: {{{2}}}>7  and {{{1}}}={{{1}}}round7  |0}}<!--
-->{{#ifexpr: {{{2}}}>8  and {{{1}}}={{{1}}}round8  |0}}<!--
-->{{#ifexpr: {{{2}}}>9  and {{{1}}}={{{1}}}round9  |0}}<!--
-->{{#ifexpr: {{{2}}}>10 and {{{1}}}={{{1}}}round10 |0}}<!--
-->{{#ifexpr: {{{2}}}>11 and {{{1}}}={{{1}}}round11 |0}}<!--
-->{{#ifexpr: {{{2}}}>12 and {{{1}}}={{{1}}}round12 |0}}<!--
--></includeonly><noinclude>{{pp-template}}Adds trailing zeros:

*{{xpd|rnd/-|2|3}}

Used by {{tiw|rnd}}:
*{{xpd|#expr:2.0004 round 3}}
*{{xpd|rnd|2.0004|3}}
</noinclude>""",

"precision/1":
    """{{precision/-1{{#expr:{{{1}}}5={{{1}}}5round7}}|{{{1}}}5}}""",

"precision/-11":
    """6-({{{1}}}={{{1}}}round2)-({{{1}}}={{{1}}}round3)-({{{1}}}={{{1}}}round4)-({{{1}}}={{{1}}}round5)-({{{1}}}={{{1}}}round6)""",
"precision/-10":
    """{{precision/-2{{#expr:{{{1}}}={{{1}}}round13}}|{{{1}}}}}""",
"args":
    """1={{{1}}}
2={{{2}}}
3={{{3}}}
""",
}


def getdb():
    return DictDB(**db)


def test_round():
    expandstr("{{rnd|2.0004|3}}", "2.000", wikidb=getdb())
    expandstr("{{rnd|0.000020004|8}}", "2.0E-5000", wikidb=getdb())
    expandstr("{{rnd|0|8}}", "0.00000000", wikidb=getdb())


def test_max_2():
    expandstr("{{max/2|-1|1}}", "1", wikidb=getdb())
    expandstr("{{max/2|1|-1}}", "1", wikidb=getdb())


def test_round_plus_1():
    expandstr("{{rnd/+|1.056|2|5-1}}", "1.06", wikidb=getdb())


def test_round_plus_2():
    expandstr("{{rnd/+|1.056|2|5}}", "5", wikidb=getdb())


def test_round_plus_3():
    expandstr("{{rnd/+|1.056|2|abc}}", "1.06", wikidb=getdb())


def test_precision_plus_1():
    expandstr("{{precision/+|0.77}}", "2", wikidb=getdb())


def test_convert_ft_in_m_float():
    expandstr("{{convert|2.5|ft|m}}", "2.5&nbsp;feet (0.76&nbsp;m)\n", wikidb=getdb())


def test_convert_ft_in_m_int():
    expandstr("{{convert|12|ft|m}}", "12&nbsp;feet (3.7&nbsp;m)\n", wikidb=getdb())


def test_round_minus():
    expandstr("{{rnd/-|0.00002|8}}", "2.0E-5000", wikidb=getdb())
