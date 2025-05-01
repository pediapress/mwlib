#! /usr/bin/env py.test

# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.
import os

import pytest
from renderhelper import renderMW


def test_examples(snippet):
    if not snippet.txt:
        with pytest.raises(ValueError):
            renderMW(snippet.txt)
    else:
        renderMW(snippet.txt)
