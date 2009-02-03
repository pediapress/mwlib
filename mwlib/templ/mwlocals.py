def get_locals_txt():
    names = """LOCALDAY LOCALDAY2 LOCALDAYNAME LOCALDOW LOCALMONTH
LOCALMONTHABBREV LOCALMONTHNAME LOCALTIME LOCALYEAR LOCALTIMESTAMP
NUMBEROFARTICLES NUMBEROFPAGES NUMBEROFFILES NUMBEROFUSERS CURRENTVERSION
"""
    names = [x for x in names.split() if x]

    return "\n----\n".join(["%s={{%s}}" % (x, x) for x in names]+["{{LOCALVARS}}\n"])

def parse_locals(localstr):
    if isinstance(localstr, str):
        localstr = unicode(localstr)
    res = {}
    for x in localstr.split("\n----\n"):
        try:
            name, val = x.split('=', 1)
        except ValueError:
            continue
        if name:
            res[name] = val
    return res
