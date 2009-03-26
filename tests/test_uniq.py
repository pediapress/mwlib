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
    
def test_empty_nowiki():
    u=uniq.Uniquifier()
    s=u.replace_tags("abc<nowiki></nowiki>def")
    assert 'UNIQ' in s
    r=u.replace_uniq(s)
    assert r=="abcdef"
