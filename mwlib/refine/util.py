
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.txt for additional licensing information.

import re

paramrx = re.compile("(?P<name>\w+) *= *(?P<value>(?:(?:\".*?\")|(?:\'.*?\')|(?:(?:\w|[%:])+)))")
def parseParams(s):
    def style2dict(s):
        res = {}
        for x in s.split(';'):
            if ':' in x:
                var, value = x.split(':', 1)
                var = var.strip().lower()
                value = value.strip()
                res[var] = value

        return res
    
    def maybeInt(v):
        try:
            return int(v)
        except:
            return v
    
    r = {}
    for name, value in paramrx.findall(s):
        if value.startswith('"') or value.startswith("'"):
            value = value[1:-1]
            
        if name.lower() == 'style':
            value = style2dict(value)
            r['style'] = value
        else:
            r[name] = maybeInt(value)
    return r
