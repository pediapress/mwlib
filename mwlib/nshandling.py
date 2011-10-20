
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

"""
namespace handling based on data extracted from the siteinfo as
returned by api.php
"""

import re


NS_MEDIA          = -2
NS_SPECIAL        = -1
NS_MAIN           =  0
NS_TALK           =  1
NS_USER           =  2
NS_USER_TALK      =  3
NS_PROJECT        =  4
NS_PROJECT_TALK   =  5
NS_FILE           =  6
NS_IMAGE          =  6
NS_FILE_TALK      =  7
NS_IMAGE_TALK     =  7
NS_MEDIAWIKI      =  8
NS_MEDIAWIKI_TALK =  9
NS_TEMPLATE       = 10
NS_TEMPLATE_TALK  = 11
NS_HELP           = 12
NS_HELP_TALK      = 13
NS_CATEGORY       = 14
NS_CATEGORY_TALK  = 15

class ilink(object):
    url = ""
    prefix = ""
    local = ""
    language = ""

def fix_wikipedia_siteinfo(siteinfo):

    # --- http://code.pediapress.com/wiki/ticket/754

    if u'\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd' in [x.get("prefix", u"")[2:] for x in siteinfo.get("interwikimap", [])]:
        print "WARNING: interwikimap contains garbage"
        from mwlib import siteinfo as simod
        en = simod.get_siteinfo("en")
        siteinfo['interwikimap'] = list(en["interwikimap"])


    prefixes = [x['prefix'] for x in siteinfo['interwikimap']]
    for p in "pnb ckb mwl mhr ace krc pcd frr koi gag bjn pfl mrj bjn rue kbd ltg xmf".split():
        
        if p in prefixes:
            return
        siteinfo['interwikimap'].append({
            'prefix': p,
            'language': p,
            'url': 'http://%s.wikipedia.org/wiki/$1' % (p, ),
            'local': '',
        })
    
# TODO: build fast lookup table for use in nshandler.splitname
class nshandler(object):
    def __init__(self, siteinfo):
        assert siteinfo is not None

        if 'general' in siteinfo and siteinfo['general'].get('server', '').endswith(".wikipedia.org") and 'interwikimap' in siteinfo:
            fix_wikipedia_siteinfo(siteinfo)

        self.siteinfo = siteinfo
        try:
            self.capitalize = self.siteinfo['general'].get('case') == 'first-letter'
        except KeyError:
            self.capitalize = True

        p = self.prefix2interwiki = {}
        for k in siteinfo.get("interwikimap", []):
            p[k["prefix"]] = k

        self.set_redirect_matcher(siteinfo)

    def set_redirect_matcher(self, siteinfo):
        self.redirect_matcher = get_redirect_matcher(siteinfo, self)

    def __getstate__(self):
        d=self.__dict__.copy()
        del d['redirect_matcher']
        return d

    def __setstate__(self, d):
        self.__dict__ = d
        self.set_redirect_matcher(self.siteinfo)

    # workaround for a copy.deepcopy bug in python 2.4
    # should be save to return the instance itself without copying
    # since it's basically immutable.
    def __deepcopy__(self, memo):
        return self
    
    def _find_namespace(self, name, defaultns=0):
        name = name.lower().strip()
        namespaces = self.siteinfo["namespaces"].values()
        for ns in namespaces:
            star = ns["*"]
            if star.lower()==name or ns.get("canonical", u"").lower()==name:
                return True, ns["id"], star
            

        aliases = self.siteinfo.get("namespacealiases", [])
        for a in aliases:
            if a["*"].lower()==name:
                nsid = a["id"]
                return True, nsid, self.siteinfo["namespaces"][str(nsid)]["*"]
                
        return False, defaultns, self.siteinfo["namespaces"][str(defaultns)]["*"]

    def get_fqname(self, title, defaultns=0):
        return self.splitname(title, defaultns=defaultns)[2]

    def maybe_capitalize(self, t):
        if self.capitalize:
            return t[0:1].upper() + t[1:]
        return t
    
    def splitname(self, title, defaultns=0):
        if not isinstance(title, unicode):
            title = unicode(title, 'utf-8')

        # if "#" in title:
        #     title = title.split("#")[0]
            
        name = re.sub(r' +', ' ', title.replace("_", " ").strip())
        if name.startswith(":"):
            name = name[1:].strip()
            defaultns = 0
            
        if ":" in name:
            ns, partial_name = name.split(":", 1)
            was_namespace, nsnum, prefix = self._find_namespace(ns, defaultns=defaultns)
            if was_namespace:
                suffix = partial_name.strip()
            else:
                suffix = name
        else:
            prefix = self.siteinfo["namespaces"][str(defaultns)]["*"]
            suffix = name
            nsnum = defaultns

        suffix=suffix.strip(u"\u200e\u200f")
        suffix=self.maybe_capitalize(suffix)
        if prefix:
            prefix += ":"
            
        return (nsnum, suffix, "%s%s" % (prefix,  suffix))

    def get_nsname_by_number(self, ns):
        return self.siteinfo["namespaces"][str(ns)]["*"]
        
    def resolve_interwiki(self, title):
        name = title.replace("_", " ").strip()
        if name.startswith(":"):
            name = name[1:].strip()
        if ":" not in name:
            return None
        prefix, suffix = name.split(":", 1)
        prefix = prefix.strip().lower()
        d = self.prefix2interwiki.get(prefix)
        if d is None:
            return None
        
        suffix = suffix.strip(" _\n\t\r").replace(" ", "_")
        retval = ilink()
        retval.__dict__.update(d)
        retval.url = retval.url.replace("$1", suffix)
        retval.partial = suffix
        return retval
        
def get_nshandler_for_lang(lang):
    if lang is None:
        lang = "de" # FIXME: we currently need this to make the tests happy
        
    # assert lang is not None, "expected some language"
    from mwlib import siteinfo
    si = siteinfo.get_siteinfo(lang)
    if si is None:
        si = siteinfo.get_siteinfo("en")
        assert si, "siteinfo-en not found"
    return nshandler(si)

def get_redirect_matcher(siteinfo, handler=None):
    redirect_rex = re.compile(r'^#Redirect:?\s*?\[\[(?P<redirect>.*?)\]\]', re.IGNORECASE)

    if handler is None:
        handler =  nshandler(siteinfo)
    
    def redirect(text):
        mo = redirect_rex.search(text)
        if mo:
            name = mo.group('redirect').split("|", 1)[0]
            name = name.split("#")[0]
            return handler.get_fqname(name)
        return None
    
    return redirect
