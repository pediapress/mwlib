import subprocess
from pathlib import Path

import pytest
from mwlib.utilities import utils

here = Path(__file__).parent


def mwzip(metabook):
    dst = metabook.with_suffix(".zip")
    subprocess.run(["mw-zip", "-x", "-m", str(metabook), "-o", str(dst)], check=True)
    return dst


def render_get_text(metabook):
    z = mwzip(metabook)
    dst = z.with_suffix(".pdf")
    subprocess.run(["mw-render", "-c", str(z), "-o", str(dst), "-w", "rl"], check=True)
    txt = utils.pdf2txt(str(dst))
    return txt


def no_redirect(mb):
    mb = here / mb
    txt = render_get_text(mb)
    print("txt:", repr(txt))
    assert "redirect" not in txt.lower(), "redirect not resolved"


@pytest.mark.integration
def test_redirect_canthus_xnet():
    no_redirect("canthus.mb.json")


@pytest.mark.integration
def test_redirect_kolumne_xnet():
    no_redirect("kolumne.mb.json")
