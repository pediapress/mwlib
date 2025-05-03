import locale
from xml.sax.saxutils import quoteattr

from mwlib.parser.templ import evaluate, magic_time, nodes


class Subst(nodes.Node):
    def flatten(self, expander, variables, res):
        name = []
        evaluate.flatten(self[0], expander, variables, name)
        name = "".join(name).strip()

        res.append(f"{{{{subst:{name}}}}}")


class SafeSubst(nodes.Template):
    def _get_args(self):
        return self[1:]


class Time(nodes.Node):
    def flatten(self, expander, variables, res):
        formats = []
        evaluate.flatten(self[0], expander, variables, formats)
        formats = "".join(formats).strip()

        if len(self) > 1:
            date_elements = []
            evaluate.flatten(self[1], expander, variables, date_elements)
            date_elements = "".join(date_elements).strip()
        else:
            date_elements = None

        res.append(magic_time.time(formats, date_elements))


class AnchorEncode(nodes.Node):
    def flatten(self, expander, variables, res):
        arg = []
        evaluate.flatten(self[0], expander, variables, arg)
        arg = "".join(arg)

        # Note: mediawiki has a bug. It tries not to touch
        # colons by replacing '.3A'
        # with the colon. However, if the original string
        # contains the substring '.3A',
        # it will also replace it with a colon. We do *not*
        # reproduce that bug here...
        import urllib.parse

        encoded_argument = (
            urllib.parse.quote_plus(arg.encode("utf-8"), ":")
            .replace("%", ".")
            .replace("+", "_")
        )
        res.append(encoded_argument)


def _rel2abs(rel, base):
    rel = rel.rstrip("/")
    if rel in ("", "."):
        return base
    if not (rel.startswith("/") or rel.startswith("./") or rel.startswith("../")):
        base = ""

    import posixpath

    path = posixpath.normpath(f"/{base}/{rel}/").strip("/")
    return path


class RelativeToAbsolute(nodes.Node):
    def flatten(self, expander, variables, res):
        arg = []
        evaluate.flatten(self[0], expander, variables, arg)
        arg = "".join(arg).strip()

        arg2 = []
        if len(self) > 1:
            evaluate.flatten(self[1], expander, variables, arg2)
        arg2 = "".join(arg2).strip()
        if not arg2:
            arg2 = expander.pagename

        res.append(_rel2abs(arg, arg2))


class Tag(nodes.Node):
    def flatten(self, expander, variables, res):
        name = []
        evaluate.flatten(self[0], expander, variables, name)
        name = "".join(name).strip()
        parameters = ""

        for parm in self[2:]:
            tmp = []
            evaluate.flatten(parm, expander, variables, tmp)
            evaluate.insert_implicit_newlines(tmp)
            tmp = "".join(tmp)
            if "=" in tmp:
                key, value = tmp.split("=", 1)
                parameters += f" {key}={quoteattr(value)}"

        tmp_res = [f"<{name}{parameters}>"]

        if len(self) > 1:
            tmp = []
            evaluate.flatten(self[1], expander, variables, tmp)
            evaluate.insert_implicit_newlines(tmp)
            tmp = "".join(tmp)
            tmp_res.append(tmp)

        tmp_res.append(f"</{name}>")
        tmp_res = "".join(tmp_res)
        tmp_res = expander.uniquifier.replace_tags(tmp_res)
        res.append(tmp_res)


class NoOutput(nodes.Node):
    def flatten(self, expander, variables, res):
        pass  # do nothing


class DefaultSort(NoOutput):
    pass


class DisplayTitle(nodes.Node):
    def flatten(self, expander, variables, res):
        name = []
        evaluate.flatten(self[0], expander, variables, name)
        name = "".join(name).strip()
        expander.magic_displaytitle = name


def reverse_format_num(val):
    try:
        return str(locale.atoi(val))
    except ValueError:
        pass

    try:
        return str(locale.atof(val))
    except ValueError:
        pass

    return val


def _format_num(val):
    try:
        val = int(val)
    except ValueError:
        pass
    else:
        return locale.format_string("%d", val, True)

    try:
        val = float(val)
    except ValueError:
        return val

    return locale.format_string("%g", val, True)


def format_num(val):
    res = _format_num(val)
    return res


class FormatNum(nodes.Node):
    def flatten(self, expander, variables, res):
        arg0 = []
        evaluate.flatten(self[0], expander, variables, arg0)
        arg0 = "".join(arg0)

        if len(self) > 1:
            arg1 = []
            evaluate.flatten(self[1], expander, variables, arg1)
            arg1 = "".join(arg1)
        else:
            arg1 = ""

        if arg1.strip() in ("r", "R"):
            res.append(reverse_format_num(arg0))
        else:
            res.append(format_num(arg0))


def make_switch_node(args):
    return nodes.SwitchNode((args[0], args[1:]))


registry = {
    "#time": Time,
    "subst": Subst,
    "safesubst": SafeSubst,
    "anchorencode": AnchorEncode,
    "#tag": Tag,
    "displaytitle": DisplayTitle,
    "defaultsort": DefaultSort,
    "#rel2abs": RelativeToAbsolute,
    "#switch": make_switch_node,
    "#if": nodes.IfNode,
    "#ifeq": nodes.IfEqNode,
    "formatnum": FormatNum,
}
