#! /usr/bin/env py.test

# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.

import pytest
from mwlib import snippets
from renderhelper import renderMW


def doit(ex):
    print("rendering", ex)
    renderMW(ex.txt)


@pytest.mark.parametrize("ex", snippets.get_all())
def test_examples(ex):
    if not ex.txt:
        with pytest.raises(ValueError):
            doit(ex)
    else:
        doit(ex)

    # FIXME: move snippets to test directory
