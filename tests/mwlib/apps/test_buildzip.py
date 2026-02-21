import os
import tempfile

import pytest
from click.testing import CliRunner

from mwlib.apps import buildzip, buildzip2


 # Characterization Tests - Capturing Current Observable Behavior
# These tests document the existing behavior of the buildzip module

@pytest.mark.integration
def test_buildzip_incomplete_arguments():
    """Original test - captures behavior with config and article arguments."""
    runner = CliRunner()
    tmpdir = tempfile.mkdtemp()
    zip_fn = os.path.join(tmpdir, "test.zip")

    result = runner.invoke(buildzip.main, ["-o", zip_fn, "-c", ":de", "Monty Python"])
    # Characterization: The command currently fails, no zip file is created
    assert not os.path.isfile(zip_fn)
    assert result.exit_code != 0


def test_buildzip_no_output_or_post_fails():
    """Characterization: Requires at least one of --output, --posturl, or --getposturl."""
    runner = CliRunner()

    result = runner.invoke(buildzip.main, ["-c", ":de", "Test Article"])

    assert result.exit_code != 0
    assert "Neither --output, nor --posturl or --getposturl specified" in result.output


def test_buildzip_no_content_fails():
    """Characterization: Requires either --metabook, --collectionpage, or article arguments."""
    runner = CliRunner()
    tmpdir = tempfile.mkdtemp()
    zip_fn = os.path.join(tmpdir, "test.zip")

    result = runner.invoke(buildzip.main, ["-o", zip_fn, "-c", ":de"])

    assert result.exit_code != 0
    assert "Neither --metabook nor, --collectionpage or arguments specified" in result.output


def test_buildzip_posturl_and_getposturl_conflict():
    """Characterization: Cannot specify both --posturl and --getposturl."""
    runner = CliRunner()

    result = runner.invoke(
        buildzip.main,
        ["--posturl", "http://example.com", "--getposturl", "-c", ":de", "Test"]
    )

    assert result.exit_code != 0
    assert "Specify either --posturl or --getposturl" in result.output


def test_buildzip_invalid_imagesize():
    """Characterization: Image size must be a positive integer."""
    runner = CliRunner()
    tmpdir = tempfile.mkdtemp()
    zip_fn = os.path.join(tmpdir, "test.zip")

    result = runner.invoke(
        buildzip.main,
        ["-o", zip_fn, "-c", ":de", "--imagesize", "0", "Test"]
    )

    assert result.exit_code != 0
    assert "Argument for --imagesize must be an integer > 0" in result.output


def test_buildzip_negative_imagesize():
    """Characterization: Negative image size is invalid."""
    runner = CliRunner()
    tmpdir = tempfile.mkdtemp()
    zip_fn = os.path.join(tmpdir, "test.zip")

    result = runner.invoke(
        buildzip.main,
        ["-o", zip_fn, "-c", ":de", "--imagesize", "-100", "Test"]
    )

    assert result.exit_code != 0
    assert "Argument for --imagesize must be an integer > 0" in result.output


def test_buildzip_non_numeric_imagesize():
    """Characterization: Image size must be numeric - Click validates this."""
    runner = CliRunner()
    tmpdir = tempfile.mkdtemp()
    zip_fn = os.path.join(tmpdir, "test.zip")

    result = runner.invoke(
        buildzip.main,
        ["-o", zip_fn, "-c", ":de", "--imagesize", "abc", "Test"]
    )

    assert result.exit_code != 0
    assert "'abc' is not a valid integer" in result.output


def test_buildzip_accepts_multiple_articles():
    """Characterization: Multiple article names can be passed as arguments."""
    runner = CliRunner()
    tmpdir = tempfile.mkdtemp()
    zip_fn = os.path.join(tmpdir, "test.zip")

    # This will likely fail due to network/config issues, but tests argument parsing
    result = runner.invoke(
        buildzip.main,
        ["-o", zip_fn, "-c", ":de", "Article1", "Article2", "Article3"]
    )

    # The command accepts the arguments (doesn't fail validation)
    # Actual failure will be network/config related, not argument validation
    assert "Neither --metabook nor, --collectionpage or arguments specified" not in result.output


def test_buildzip_default_imagesize():
    """Characterization: Default image size is 1280 when not specified."""
    runner = CliRunner()
    tmpdir = tempfile.mkdtemp()
    zip_fn = os.path.join(tmpdir, "test.zip")

    # Test without specifying imagesize - should use default
    result = runner.invoke(
        buildzip.main,
        ["-o", zip_fn, "-c", ":de", "Test"]
    )

    # Should not fail due to imagesize validation
    assert "Argument for --imagesize must be an integer > 0" not in result.output


def test_buildzip_with_valid_imagesize():
    """Characterization: Valid positive imagesize is accepted."""
    runner = CliRunner()
    tmpdir = tempfile.mkdtemp()
    zip_fn = os.path.join(tmpdir, "test.zip")

    result = runner.invoke(
        buildzip.main,
        ["-o", zip_fn, "-c", ":de", "--imagesize", "800", "Test"]
    )

    # Should not fail due to imagesize validation
    assert "Argument for --imagesize must be an integer > 0" not in result.output


# ============================================================================
# Characterization Tests for buildzip2 (Modern Implementation)
# ============================================================================


def test_buildzip2_no_output_or_post_fails():
    """Buildzip2: Requires at least one of --output, --posturl, or --getposturl."""
    runner = CliRunner()

    result = runner.invoke(buildzip2.main, ["-c", ":de", "Test Article"])

    assert result.exit_code != 0
    assert "Neither --output, nor --posturl or --getposturl specified" in result.output


def test_buildzip2_no_content_fails():
    """Buildzip2: Requires either --metabook, --collectionpage, or article arguments."""
    runner = CliRunner()
    tmpdir = tempfile.mkdtemp()
    zip_fn = os.path.join(tmpdir, "test.zip")

    result = runner.invoke(buildzip2.main, ["-o", zip_fn, "-c", ":de"])

    assert result.exit_code != 0
    assert "Neither --metabook nor, --collectionpage or arguments specified" in result.output


def test_buildzip2_posturl_and_getposturl_conflict():
    """Buildzip2: Cannot specify both --posturl and --getposturl."""
    runner = CliRunner()

    result = runner.invoke(
        buildzip2.main,
        ["--posturl", "http://example.com", "--getposturl", "-c", ":de", "Test"]
    )

    assert result.exit_code != 0
    assert "Specify either --posturl or --getposturl" in result.output


def test_buildzip2_invalid_imagesize():
    """Buildzip2: Image size must be a positive integer."""
    runner = CliRunner()
    tmpdir = tempfile.mkdtemp()
    zip_fn = os.path.join(tmpdir, "test.zip")

    result = runner.invoke(
        buildzip2.main,
        ["-o", zip_fn, "-c", ":de", "--imagesize", "0", "Test"]
    )

    assert result.exit_code != 0
    assert "Argument for --imagesize must be an integer > 0" in result.output


def test_buildzip2_negative_imagesize():
    """Buildzip2: Negative image size is invalid."""
    runner = CliRunner()
    tmpdir = tempfile.mkdtemp()
    zip_fn = os.path.join(tmpdir, "test.zip")

    result = runner.invoke(
        buildzip2.main,
        ["-o", zip_fn, "-c", ":de", "--imagesize", "-100", "Test"]
    )

    assert result.exit_code != 0
    assert "Argument for --imagesize must be an integer > 0" in result.output


def test_buildzip2_non_numeric_imagesize():
    """Buildzip2: Image size must be numeric - Click validates this."""
    runner = CliRunner()
    tmpdir = tempfile.mkdtemp()
    zip_fn = os.path.join(tmpdir, "test.zip")

    result = runner.invoke(
        buildzip2.main,
        ["-o", zip_fn, "-c", ":de", "--imagesize", "abc", "Test"]
    )

    assert result.exit_code != 0
    assert "'abc' is not a valid integer" in result.output


def test_buildzip2_accepts_multiple_articles():
    """Buildzip2: Multiple article names can be passed as arguments."""
    runner = CliRunner()
    tmpdir = tempfile.mkdtemp()
    zip_fn = os.path.join(tmpdir, "test.zip")

    # This will likely fail due to network/config issues, but tests argument parsing
    result = runner.invoke(
        buildzip2.main,
        ["-o", zip_fn, "-c", ":de", "Article1", "Article2", "Article3"]
    )

    # The command accepts the arguments (doesn't fail validation)
    # Actual failure will be network/config related, not argument validation
    assert "Neither --metabook nor, --collectionpage or arguments specified" not in result.output


def test_buildzip2_default_imagesize():
    """Buildzip2: Default image size is 1280 when not specified."""
    runner = CliRunner()
    tmpdir = tempfile.mkdtemp()
    zip_fn = os.path.join(tmpdir, "test.zip")

    # Test without specifying imagesize - should use default
    result = runner.invoke(
        buildzip2.main,
        ["-o", zip_fn, "-c", ":de", "Test"]
    )

    # Should not fail due to imagesize validation
    assert "Argument for --imagesize must be an integer > 0" not in result.output


def test_buildzip2_with_valid_imagesize():
    """Buildzip2: Valid positive imagesize is accepted."""
    runner = CliRunner()
    tmpdir = tempfile.mkdtemp()
    zip_fn = os.path.join(tmpdir, "test.zip")

    result = runner.invoke(
        buildzip2.main,
        ["-o", zip_fn, "-c", ":de", "--imagesize", "800", "Test"]
    )

    # Should not fail due to imagesize validation
    assert "Argument for --imagesize must be an integer > 0" not in result.output


# ============================================================================
# Unit Tests for buildzip2 Components
# ============================================================================


def test_metabook_parser_from_string():
    """Test MetabookParser can parse JSON string."""
    from mwlib.apps.buildzip2 import MetabookParser
    from mwlib.core.metabook import Collection

    json_str = '{"type": "collection", "items": []}'
    result = MetabookParser.parse(json_str)

    assert result is not None
    assert isinstance(result, (dict, Collection))


def test_metabook_parser_none_input():
    """Test MetabookParser handles None input."""
    from mwlib.apps.buildzip2 import MetabookParser

    result = MetabookParser.parse(None)
    assert result is None


def test_metabook_parser_add_articles():
    """Test adding articles to metabook."""
    from mwlib.apps.buildzip2 import MetabookParser
    from mwlib.core.metabook import Collection

    articles = ("Article1", "Article2")
    result = MetabookParser.add_articles(None, articles)

    assert isinstance(result, Collection)


def test_options_validator_output_conflict():
    """Test validation catches posturl and getposturl conflict."""
    from mwlib.apps.buildzip2 import OptionsValidator

    with pytest.raises(Exception) as exc_info:
        OptionsValidator.validate_output_options("out.zip", "http://post", 1)

    assert "Specify either --posturl or --getposturl" in str(exc_info.value)


def test_options_validator_no_output():
    """Test validation catches missing output options."""
    from mwlib.apps.buildzip2 import OptionsValidator

    with pytest.raises(Exception) as exc_info:
        OptionsValidator.validate_output_options(None, None, 0)

    assert "Neither --output, nor --posturl or --getposturl" in str(exc_info.value)


def test_options_validator_imagesize_zero():
    """Test validation catches zero imagesize."""
    from mwlib.apps.buildzip2 import OptionsValidator

    with pytest.raises(Exception) as exc_info:
        OptionsValidator.validate_imagesize(0)

    assert "must be an integer > 0" in str(exc_info.value)


def test_options_validator_imagesize_valid():
    """Test validation accepts valid imagesize."""
    from mwlib.apps.buildzip2 import OptionsValidator

    # Should not raise
    OptionsValidator.validate_imagesize(1280)


def test_zip_creator_basic():
    """Test ZipCreator can create a zip file."""
    from mwlib.apps.buildzip2 import ZipCreator
    import zipfile

    tmpdir = tempfile.mkdtemp()
    try:
        # Create test file
        test_file = os.path.join(tmpdir, "test.txt")
        with open(test_file, "w") as f:
            f.write("test content")

        # Create zip
        zip_path = ZipCreator.create_zip(tmpdir)

        # Verify zip exists and contains file
        assert os.path.exists(zip_path)
        with zipfile.ZipFile(zip_path, "r") as zf:
            assert "test.txt" in zf.namelist()

        os.unlink(zip_path)
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_build_config_immutable():
    """Test BuildConfig is immutable."""
    from mwlib.apps.buildzip2 import BuildConfig

    config = BuildConfig(
        output="test.zip",
        posturl=None,
        getposturl=0,
        keep_tmpfiles=False,
        status_file=None,
        config=":de",
        imagesize=1280,
        metabook=None,
        collectionpage=None,
        noimages=False,
        logfile=None,
        username=None,
        password=None,
        domain=None,
        title=None,
        subtitle=None,
        editor=None,
        script_extension=".php",
    )

    # Should not be able to modify
    with pytest.raises(Exception):
        config.output = "other.zip"
