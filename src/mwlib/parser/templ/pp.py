# Copyright (c) 2007-2009 PediaPress GmbH
# See README.md for additional licensing information.
import re


def rxc(pattern_string):
    return re.compile(pattern_string, re.DOTALL | re.IGNORECASE)


onlyincluderx = rxc(r"<onlyinclude>(.*?)</onlyinclude>")
noincluderx = rxc(r"<noinclude(?:\s[^<>]*)?>.*?(</noinclude>|$)")
includeonlyrx = rxc(r"<includeonly(?:\s[^<>]*)?>.*?(?:</includeonly>|$)")


def get_remove_tags(tags):
    compiled_regex = rxc(r"</?(%s)(?:\s[^<>]*)?>" % ("|".join(tags)))
    return lambda input_string: compiled_regex.sub("", input_string)


remove_not_included = get_remove_tags(["onlyinclude", "noinclude"])


def preprocess(txt, included=True):
    if included:
        txt = noincluderx.sub("", txt)

        if "<onlyinclude>" in txt:
            # if onlyinclude tags are used, only use text between those tags.
            # template 'legend' is a example
            txt = "".join(onlyincluderx.findall(txt))
    else:
        txt = includeonlyrx.sub("", txt)
        txt = remove_not_included(txt)

    return txt
