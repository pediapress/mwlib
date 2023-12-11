#! /usr/bin/env py.test

import gettext
import os

import pytest
from mwlib.writers import rl as mwlib_rl


def get_translation(lang):
    localedir = os.path.join(mwlib_rl.__path__[0], "locale")
    translation = gettext.translation("mwlib.rl", localedir, [lang])
    translation.install()
    return translation


@pytest.mark.parametrize(("lang",), [("de",), ("en",), ("nl",)])
def test_translation_exists(lang):
    get_translation(lang)
