#! /usr/bin/env py.test

import os

from mwlib import utils

here = os.path.dirname(__file__)


def mwzip(metabook):
    os.environ["S"] = metabook
    dst = os.environ["D"] = metabook.replace(".mb.json", ".zip")
    err = os.system("mw-zip -x -m $S -o $D")
    assert err == 0, "mw-zip failed"
    return dst


def render_get_text(metabook):
    z = mwzip(metabook)
    os.environ["S"] = z
    dst = os.environ["D"] = z.replace(".zip",  ".pdf")
    err = os.system("mw-render -c $S -o $D -w rl")
    assert err == 0, "mw-render failed"
    txt = utils.pdf2txt(dst)
    return txt


def no_redirect(mb):
    mb = os.path.join(here, mb)
    txt = render_get_text(mb)
    print "txt:",  repr(txt)
    assert "redirect" not in txt.lower(), "redirect not resolved"


def test_redirect_canthus_xnet():
    no_redirect("canthus.mb.json")


def test_redirect_kolumne_xnet():
    no_redirect("kolumne.mb.json")
