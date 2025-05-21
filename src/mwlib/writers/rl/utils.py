import logging
import traceback

from reportlab.pdfbase.pdfdoc import PDFDictionary
from reportlab.platypus.paragraph import Paragraph

from mwlib.writers.rl.pdfstyles import text_style

log = logging.getLogger("rlwriter")


def check_reportlab():
    try:
        PDFDictionary.__getitem__
    except AttributeError as exc:
        raise ImportError(
            "you need to have the svn version of reportlab installed"
        ) from exc


def _flatten(node):
    result = []
    for element in node:
        if hasattr(element, "__iter__") and not isinstance(element, str):
            result.extend(_flatten(element))
        else:
            result.append(element)
    return result


def is_inline(objs):
    return all(isinstance(obj, str) for obj in _flatten(objs))


def build_paragraph(txt_list, style=text_style(), txt_style=None):
    _txt = "".join(txt_list)
    _txt = _txt.strip()
    if txt_style:
        _txt = "{start}{txt}{end}".format(
            start="".join(txt_style["start"]),
            end="".join(txt_style["end"]),
            txt=_txt,
        )
    if len(_txt) > 0:
        try:
            return [Paragraph(_txt, style)]
        except Exception:
            traceback.print_exc()
            log.warning("reportlab paragraph error:", repr(_txt))
            return []
    else:
        return []
