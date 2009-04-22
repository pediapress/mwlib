
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.txt for additional licensing information.

"""
namespace handling based on data extracted from the siteinfo.
replace namespace.py
"""

class nsmapper(object):
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

        if prefix:
            prefix += ":"
        return "%s%s%s" % (prefix,  suffix[:1].upper(), suffix[1:])
