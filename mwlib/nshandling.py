
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.txt for additional licensing information.

"""
namespace handling based on data extracted from the siteinfo as
returned by api.php
"""

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

class nshandler(object):
    def __init__(self, siteinfo):
        self.siteinfo = siteinfo
    
    def _find_namespace(self, name, defaultns=0):
        name = name.lower().strip()
        namespaces = self.siteinfo["namespaces"].values()
        for ns in namespaces:
            star = ns["*"]
            if star.lower()==name or ns.get("canonical", u"").lower()==name:
                return True, ns["id"], star
            

        aliases = self.siteinfo["namespacealiases"]
        for a in aliases:
            if a["*"].lower()==name:
                nsid = a["id"]
                return True, nsid, self.siteinfo["namespaces"][str(nsid)]["*"]
                
        return False, defaultns, self.siteinfo["namespaces"][str(defaultns)]["*"]

    def get_fqname(self, title, defaultns=0):
        return self.splitname(title, defaultns=defaultns)[2]
    
    def splitname(self, title, defaultns=0):
        name = title.replace("_", " ").strip()
        if name.startswith(":"):
            name = name[1:].strip()

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

        suffix="%s%s" % (suffix[:1].upper(), suffix[1:])
        if prefix:
            prefix += ":"
            
        return (nsnum, suffix, "%s%s" % (prefix,  suffix))
    
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
