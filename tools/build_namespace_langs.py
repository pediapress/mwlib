#! /usr/bin/env python

"""Build mwlib/namespace_langs.py from MediaWiki SVN checkout

Call this with mediawiki (top-level) directory as only argument,
pipe output to namespace_langs.py.
"""

import os
import re
import sys

from mwlib import namespace

filename_rex = re.compile(r'^Messages(?P<lang>\w\w\w?)\.php$')
start_names_rex = re.compile(r'^\$namespaceNames = array\($')
start_aliases_rex = re.compile(r'^\$namespaceAliases = array\($')
const2name_rex = re.compile('^\\s*(?P<const>NS_\w+)\\s*=>\\s*["\'](?P<name>\S+)["\']\s*,?\s*$')
name2const_rex = re.compile('^\\s*["\'](?P<name>\S+)["\']\\s*=>\\s*(?P<const>NS_\w+)\s*,?\s*$')
end_rex = re.compile(r'^\);$')

def parse_namespace_names(fn):
    ns2name = {}
    started = False
    for line in open(fn, 'rb'):
        if not started:
            if start_names_rex.match(line):
                started = True
            else:
                continue
        if end_rex.match(line):
            break
        mo = const2name_rex.match(line)
        if mo is None:
            continue
        try:
            nsnum = getattr(namespace, mo.group('const'))
        except AttributeError:
            continue
        name = unicode(mo.group('name'), 'utf-8')
        if nsnum == namespace.NS_PROJECT_TALK:
            name = name.replace('$1', '%s')
        ns2name[nsnum] = name
    else:
        # no namespace names found in this file
        return None
    return ns2name

def parse_namespace_aliases(fn):
    name2ns = {}
    started = False
    for line in open(fn, 'rb'):
        if not started:
            if start_aliases_rex.match(line):
                started = True
            else:
                continue
        if end_rex.match(line):
            break
        mo = name2const_rex.match(line)
        if mo is None:
            continue
        try:
            nsnum = getattr(namespace, mo.group('const'))
        except AttributeError:
            continue
        name = unicode(mo.group('name'), 'utf-8')
        name2ns[name] = nsnum
    else:
        # no namespace aliases found in this file
        return {}
    
    return name2ns

def get_ns_list(names, aliases):
    for name, nsnum in aliases.items():
        try:
            v = names[nsnum]
        except KeyError:
            return None
        if isinstance(v, unicode):
            names[nsnum] = (v, name)
        else:
            names[nsnum] = v + (name,)
    
    proj_talk_name = names.get(namespace.NS_PROJECT_TALK, u'%s_talk')
    try:
        return [names[nsnum] for nsnum in namespace._lang_ns_data_keys] + [proj_talk_name]
    except KeyError, e:
        return None

def main(argv):
    if len(argv) != 2:
        sys.exit('Usage: %s MEDIAWIKIDIR' % argv[0])
    
    msgsdir = os.path.join(argv[1], 'languages', 'messages')
    assert os.path.isdir(msgsdir), '%r is not a directory' % msgsdir
    
    lang_ns_data = {}
    for fn in os.listdir(msgsdir):
        mo = filename_rex.match(fn)
        if mo is None:
            continue
        lang = mo.group('lang').lower()
        if lang == 'en':
            # English is special: aliases are handled by other means etc.
            continue
        p = os.path.join(msgsdir, fn)
        names = parse_namespace_names(p)
        if not names:
            continue
        lst = get_ns_list(names, parse_namespace_aliases(p))
        if lst:
            lang_ns_data[lang] = lst
    
    lang_ns_data['en'] = [u'Talk', u'User', u'User_talk', (u'File', u'Image'), (u'File_talk', u'Image talk'), u'MediaWiki', u'MediaWiki_talk', u'Template', u'Template_talk', u'Help', u'Help_talk', u'Category', u'Category_talk', u'Special', u'Media', u'%s_talk']
    
    s = ['lang_ns_data = {']
    for lang in sorted(lang_ns_data.keys()):
        s.append("'%s': %r," % (lang, lang_ns_data[lang]))
    s.append('}')
    s = '\n'.join(s)
    
    print s

if __name__ == '__main__':
    main(sys.argv)
