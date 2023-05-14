#! /usr/bin/env py.test

import os, pytest, gettext


def get_translation(lang):
    import mwlib.rl
    localedir = os.path.join(mwlib.rl.__path__[0], "locale")
    translation = gettext.translation('mwlib.rl', localedir, [lang])
    translation.install(unicode=True)
    return translation


@pytest.mark.parametrize(("lang", ),
                         [("de",), ("en",), ("nl",)])
def test_translation_exists(lang):
    get_translation(lang)
