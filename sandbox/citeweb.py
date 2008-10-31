#! /usr/bin/env python
# -*- coding: utf-8 -*-
"""
measure template expansion performance
"""

citeweb=u"""
<includeonly>{{
#if: {{#if: {{{url|}}} | {{#if: {{{title|}}} |1}}}}
  ||You must specify  '''''title = ''''' and '''''url = ''''' when using {{[[Template:cite web|cite web]]}}.
{{#if: {{NAMESPACE}}|| [[Category:Articles with broken citations]]}}
}}{{
#if: {{{archiveurl|}}}{{{archivedate|}}} 
  | {{#if: {{#if: {{{archiveurl|}}}| {{#if: {{{archivedate|}}} |1}}}}
    ||You must specify '''''archiveurl = ''''' and '''''archivedate = ''''' when using {{[[Template:cite web|cite web]]}}.
{{#if: {{NAMESPACE}}|| [[Category:Articles with broken citations]]}}
}}
}}{{#if: {{{author|}}}{{{last|}}}
  | {{#if: {{{authorlink|}}}
    | [[{{{authorlink}}}|{{#if: {{{last|}}}
      | {{{last}}}{{#if: {{{first|}}} | , {{{first}}} }}
      | {{{author}}}
    }}]]
    | {{#if: {{{last|}}}
      | {{{last}}}{{#if: {{{first|}}} | , {{{first}}} }}
      | {{{author}}}
    }}
  }}
}}{{#if: {{{author|}}}{{{last|}}}
  | {{#if: {{{coauthors|}}}| <nowiki>;</nowiki>&#32;{{{coauthors}}} }}
}}{{#if: {{{author|}}}{{{last|}}}|
    {{#if: {{{date|}}}
    | &#32;({{#ifeq:{{#time:Y-m-d|{{{date}}}}}|{{{date}}}|[[{{{date}}}]]|{{{date}}}}})
    | {{#if: {{{year|}}}
      | {{#if: {{{month|}}}
        | &#32;({{{month}}} {{{year}}})
        | &#32;({{{year}}})
      }}
    }}
  |}}
}}{{#if: {{{last|}}}{{{author|}}}
  | .&#32;}}{{
  #if: {{{editor|}}}
  | &#32;{{{editor}}}: 
}}{{#if: {{{archiveurl|}}}
    | {{#if: {{{archiveurl|}}} | {{#if: {{{title|}}} | [{{{archiveurl}}} {{{title}}}] }}}}
    | {{#if: {{{url|}}} | {{#if: {{{title|}}} | [{{{url}}} {{{title}}}] }}}}
}}{{#if: {{{format|}}} | &#32;({{{format|}}})
}}{{#if: {{{language|}}} | &#32;<span style="color:#555;">({{{language}}})</span> 
}}{{#if: {{{work|}}}
  | .&#32;''{{{work}}}''
}}{{#if: {{{pages|}}}
  | &#32;{{{pages}}}
}}{{#if: {{{publisher|}}}
  | .&#32;{{{publisher}}}{{#if: {{{author|}}}{{{last|}}}
    | 
    | {{#if: {{{date|}}}{{{year|}}}{{{month|}}} || }}
  }}
}}{{#if: {{{author|}}}{{{last|}}}
  ||{{#if: {{{date|}}}
    | &#32;({{#ifeq:{{#time:Y-m-d|{{{date}}}}}|{{{date}}}|[[{{{date}}}]]|{{#ifeq:{{#time:Y-m-d|{{{date}}}}}|1970-01-01|[[{{{date}}}]]|{{{date}}}}}}})
    | {{#if: {{{year|}}}
      | {{#if: {{{month|}}}
        | &#32;({{{month}}} {{{year}}})
        | &#32;({{{year}}})
      }}
    }}
  }}
}}.{{#if: {{{archivedate|}}}
  | &#32;Archived from [{{{url}}} the original] on [[{{{archivedate}}}]].
}}{{#if: {{{doi|}}} 
  | &#32;[[Digital object identifier|DOI]]:[http://dx.doi.org/{{{doi|{{{doilabel|}}}}}} {{{doi}}}].
}}{{#if: {{{accessdate|}}}
  | &#32;Retrieved on [[{{{accessdate}}}]]{{#if: {{{accessyear|}}} | , [[{{{accessyear}}}]] }}.
}}{{#if: {{{accessmonthday|}}}
  | &#32;Retrieved on {{{accessmonthday}}}{{#if: {{{accessyear|}}} | , {{{accessyear}}} }}.
}}{{#if: {{{accessdaymonth|}}}
  | &#32;Retrieved on {{{accessdaymonth}}}{{#if: {{{accessyear|}}} | &#32;{{{accessyear}}} }}.
}}{{#if: {{{quote|}}} 
  | &nbsp;“{{{quote}}}”
}}</includeonly><noinclude>

{{pp-template|small=yes}}
{{Documentation}}
<!-- PLEASE ADD CATEGORIES AND INTERWIKIS TO THE /doc SUBPAGE, THANKS -->
</noinclude>
"""


import time
from mwlib import expander

snippet = """
{{citeweb|url=http://www.webbyawards.com/webbys/winners-2004.php|title=Webby Awards 2004|publisher=The International Academy of Digital Arts and Sciences|date=2004|accessdate=2007-06-19}}
"""

db=expander.DictDB(citeweb=citeweb)
e=expander.Expander(snippet*1000, pagename='test', wikidb=db)
stime=time.time()
e.expandTemplates()
print time.time()-stime
