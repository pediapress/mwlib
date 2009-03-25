#! /usr/bin/env py.test

from mwlib import utoken, uniq

def test_self_closing():
    u=uniq.Uniquifier()
    s=u.replace_tags("""
<ref />
----
<ref>
</ref>
""")
    assert s.count("UNIQ")==2
    
