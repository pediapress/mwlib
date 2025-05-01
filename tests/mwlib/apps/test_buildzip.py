import os
import tempfile

import pytest
from click.testing import CliRunner

from mwlib.apps import buildzip


@pytest.mark.integration
def test_buildzip_incomplete_arguments():
    runner = CliRunner()
    tmpdir = tempfile.mkdtemp()
    zip_fn = os.path.join(tmpdir, "test.zip")

    runner.invoke(buildzip.main, ["-o", zip_fn, "-c", ":de", "Monty Python"])
    assert os.path.isfile(zip_fn)
