def get_locals_txt():
    names = """LOCALDAY LOCALDAY2 LOCALDAYNAME LOCALDOW LOCALMONTH
LOCALMONTHABBREV LOCALMONTHNAME LOCALTIME LOCALYEAR LOCALTIMESTAMP
NUMBEROFARTICLES NUMBEROFPAGES NUMBEROFFILES NUMBEROFUSERS CURRENTVERSION
"""
    names = [x for x in names.split() if x]

    return "\n----\n".join([f"{x}={{{{{x}}}}}" for x in names] + ["{{LOCALVARS}}\n"])


def parse_locals(local_str):
    if isinstance(local_str, str):
        local_str = str(local_str)
    res = {}
    for entry in local_str.split("\n----\n"):
        try:
            name, val = entry.split("=", 1)
        except ValueError:
            continue
        if name:
            res[name] = val
    return res
