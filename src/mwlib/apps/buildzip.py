# Copyright (c) 2007-2026 PediaPress GmbH
# See README.md for additional licensing information.

"""mz-zip - Modern, maintainable implementation with clean architecture"""

import contextlib
import logging
import os
import shutil
import sys
import tempfile
import time
import webbrowser
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import click

from mwlib.apps.make_nuwiki import make_nuwiki
from mwlib.apps.utils import create_zip_from_wiki_env, make_wiki_env_from_options
from mwlib.core.metabook import Collection
from mwlib.network.podclient import PODClient, podclient_from_serviceurl
from mwlib.utils import linuxmem, unorganized
from mwlib.utils import myjson as json
from mwlib.utils.log import setup_console_logging

log = logging.getLogger(__name__)

USE_HELP_TEXT = "Use --help for usage information."


# ============================================================================
# Domain Models (Pure Data, No Side Effects)
# ============================================================================


@dataclass(frozen=True)
class BuildConfig:
    """Immutable configuration for zip build process."""

    output: Optional[str]
    posturl: Optional[str]
    getposturl: int
    keep_tmpfiles: bool
    status_file: Optional[str]
    config: Optional[str]
    imagesize: int
    metabook: Any
    collectionpage: Optional[str]
    noimages: bool
    logfile: Optional[str]
    username: Optional[str]
    password: Optional[str]
    domain: Optional[str]
    title: Optional[str]
    subtitle: Optional[str]
    editor: Optional[str]
    script_extension: str


@dataclass
class BuildResult:
    """Result of the build process."""

    output_path: Optional[str]
    success: bool
    error: Optional[Exception] = None


# ============================================================================
# Metabook Parser (Parsing Logic Separated)
# ============================================================================


class MetabookParser:
    """Parse metabook from JSON string or file."""

    @staticmethod
    def parse(metabook_input: Optional[str]) -> Optional[Collection]:
        """Parse metabook from JSON string or file path."""
        if not metabook_input:
            return None

        if "{" in metabook_input and "}" in metabook_input:
            return json.loads(metabook_input)
        else:
            with open(metabook_input, encoding="utf-8") as f:
                return json.load(f)

    @staticmethod
    def add_articles(metabook: Optional[Collection], article_titles: tuple) -> Collection:
        """Add article titles to metabook (creates new if needed)."""
        if not article_titles:
            return metabook

        result = metabook or Collection()
        for title in article_titles:
            result.append_article(title)
        return result


# ============================================================================
# Options Validator (Pure Validation Functions)
# ============================================================================


class OptionsValidator:
    """Pure validation functions for CLI options."""

    @staticmethod
    def validate_output_options(
        output: Optional[str], posturl: Optional[str], getposturl: int
    ) -> None:
        """Validate output destination options.

        Complexity: 3 (two if statements)
        """
        if posturl and getposturl:
            raise click.ClickException(
                "Specify either --posturl or --getposturl.\n" + USE_HELP_TEXT
            )
        if not posturl and not getposturl and not output:
            raise click.ClickException(
                "Neither --output, nor --posturl or --getposturl specified.\n" + USE_HELP_TEXT
            )

    @staticmethod
    def validate_content_options(
        metabook: Optional[Collection], collectionpage: Optional[str]
    ) -> None:
        """Validate content source options."""
        if metabook is None and collectionpage is None:
            raise click.ClickException(
                "Neither --metabook nor, --collectionpage or arguments specified.\n"
                + USE_HELP_TEXT
            )

    @staticmethod
    def validate_imagesize(imagesize: int) -> None:
        """Validate imagesize parameter."""
        try:
            size = int(imagesize)
            if size <= 0:
                raise ValueError()
        except (ValueError, TypeError):
            raise click.ClickException("Argument for --imagesize must be an integer > 0.")


# ============================================================================
# Temporary Directory Manager (Resource Management)
# ============================================================================


class TempDirManager:
    """Context manager for temporary directory lifecycle."""

    def __init__(self, output_path: Optional[str], keep_tmpfiles: bool):
        """Initialize temp dir manager."""
        self.output_path = output_path
        self.keep_tmpfiles = keep_tmpfiles
        self.tmpdir: Optional[str] = None

    def __enter__(self) -> str:
        """Create temporary directory."""
        if self.output_path:
            dir_path = os.path.dirname(self.output_path)
            self.tmpdir = tempfile.mkdtemp(dir=dir_path)
        else:
            self.tmpdir = tempfile.mkdtemp()
        log.info(f"created tmpdir: {self.tmpdir}")
        return self.tmpdir

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cleanup temporary directory."""
        if self.tmpdir:
            if not self.keep_tmpfiles:
                log.info(f"removing tmpdir {self.tmpdir!r}")
                shutil.rmtree(self.tmpdir, ignore_errors=True)
            else:
                log.info(f"keeping tmpdir {self.tmpdir!r}")

        if sys.platform in ("linux2", "linux3"):
            linuxmem.report()


# ============================================================================
# Zip Creator (Single Responsibility: Create Zip Archives)
# ============================================================================


class ZipCreator:
    """Create zip archives from directories."""

    @staticmethod
    def create_zip(source_dir: str, output_path: Optional[str] = None) -> str:
        """Create zip file from directory.

        Returns: Path to created zip file
        """
        if output_path:
            fd, temp_zip = tempfile.mkstemp(suffix=".zip", dir=os.path.dirname(output_path))
        else:
            fd, temp_zip = tempfile.mkstemp(suffix=".zip")

        os.close(fd)

        try:
            ZipCreator._write_zip(source_dir, temp_zip)
            if output_path:
                os.rename(temp_zip, output_path)
                return output_path
            return temp_zip
        except Exception:
            unorganized.safe_unlink(temp_zip)
            raise

    @staticmethod
    def _write_zip(source_dir: str, zip_path: str) -> None:
        """Write directory contents to zip file."""
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for dirpath, _, files in os.walk(source_dir):
                for filename in files:
                    filepath = os.path.join(dirpath, filename)
                    arcname = os.path.relpath(filepath, source_dir)
                    zf.write(filepath, arcname.replace("\\", "/"))


# ============================================================================
# POD Client Factory (Separate Business Logic from Browser Launch)
# ============================================================================


class PodClientFactory:
    """Factory for creating POD clients."""

    @staticmethod
    def create_client(posturl: Optional[str], getposturl: int) -> Optional[PODClient]:
        """Create POD client based on options."""
        if posturl:
            return PODClient(posturl)
        elif getposturl:
            service_url = PodClientFactory._get_service_url(getposturl)
            client = podclient_from_serviceurl(service_url)
            PodClientFactory._launch_browser(client.redirecturl)
            return client
        return None

    @staticmethod
    def _get_service_url(getposturl: int) -> str:
        """Get service URL based on getposturl count."""
        if getposturl > 1:
            return "https://test.pediapress.com/api/collections/"
        return "https://pediapress.com/api/collections/"

    @staticmethod
    def _launch_browser(url: str) -> None:
        """Launch browser in forked process."""
        pid = os.fork()
        if not pid:
            try:
                webbrowser.open(url)
            finally:
                os._exit(os.EX_OK)

        time.sleep(1)
        with contextlib.suppress(OSError):
            os.kill(pid, 9)


# ============================================================================
# Zip Builder (Business Logic Orchestrator)
# ============================================================================


class ZipBuilder:
    """Orchestrates the zip building process."""

    def __init__(self, config: BuildConfig):
        """Initialize builder with configuration."""
        self.config = config

    def build(self, pod_client: Optional[PODClient]) -> BuildResult:
        """Execute the build process."""
        try:
            wiki_options = self._create_wiki_options()
            env = make_wiki_env_from_options(
                metabook=self.config.metabook, wiki_options=wiki_options
            )

            with TempDirManager(self.config.output, self.config.keep_tmpfiles) as tmpdir:
                output_path = self._build_zip(tmpdir, env, wiki_options, pod_client)
                return BuildResult(output_path=output_path, success=True)

        except Exception as e:
            log.exception("Build failed")
            return BuildResult(output_path=None, success=False, error=e)

    def _create_wiki_options(self) -> dict:
        """Create wiki options dictionary from config."""
        return {
            "output": self.config.output,
            "posturl": self.config.posturl,
            "getposturl": self.config.getposturl,
            "keep_tmpfiles": self.config.keep_tmpfiles,
            "status_file": self.config.status_file,
            "config": self.config.config,
            "imagesize": self.config.imagesize,
            "collectionpage": self.config.collectionpage,
            "noimages": self.config.noimages,
            "logfile": self.config.logfile,
            "username": self.config.username,
            "password": self.config.password,
            "domain": self.config.domain,
            "title": self.config.title,
            "subtitle": self.config.subtitle,
            "editor": self.config.editor,
            "script_extension": self.config.script_extension,
            "metabook": self.config.metabook,
        }

    def _build_zip(
        self, tmpdir: str, env: Any, wiki_options: dict, pod_client: Optional[PODClient]
    ) -> Optional[str]:
        """Build the zip file."""
        nuwiki_dir = os.path.join(tmpdir, "nuwiki")
        log.info(f"creating nuwiki in {nuwiki_dir!r}")

        status = create_zip_from_wiki_env(env, pod_client, wiki_options, self._make_zip_callback)

        zip_path = ZipCreator.create_zip(nuwiki_dir, self.config.output)

        if pod_client and status:
            status(status="uploading", progress=0)
            pod_client.post_zipfile(zip_path)

        return zip_path

    def _make_zip_callback(
        self, wiki_options: dict, metabook: Any, pod_client: Any, status: Any
    ) -> str:
        """Callback for create_zip_from_wiki_env."""
        # This is called by create_zip_from_wiki_env to create nuwiki
        tmpdir = tempfile.mkdtemp()
        fsdir = os.path.join(tmpdir, "nuwiki")
        make_nuwiki(
            fsdir=fsdir,
            metabook=metabook,
            wiki_options=wiki_options,
            pod_client=pod_client,
            status=status,
        )
        return fsdir


# ============================================================================
# CLI Entry Point (Thin Wrapper)
# ============================================================================


@click.command()
@click.option("-o", "--output", help="write output to OUTPUT")
@click.option("-p", "--posturl", help="http post to POSTURL (directly)")
@click.option(
    "-g",
    "--getposturl",
    help="get POST URL from PediaPress.com, open upload page in webbrowser",
    count=True,
)
@click.option(
    "--keep-tmpfiles",
    is_flag=True,
    default=False,
    help="don't remove  temporary files like images",
)
@click.option("-s", "--status-file", help="write status/progress info to this file")
@click.option(
    "-c",
    "--config",
    help="configuration file, ZIP file or base URL",
)
@click.option(
    "-i",
    "--imagesize",
    default=1280,
    help="max. pixel size (width or height) for images (default: 1200)",
)
@click.option(
    "-m",
    "--metabook",
    help="JSON encoded text file with article collection",
)
@click.option(
    "--collectionpage",
    help="Title of a collection page",
)
@click.option(
    "-x",
    "--noimages",
    is_flag=True,
    help="exclude images",
)
@click.option(
    "-l",
    "--logfile",
    help="log to logfile",
)
@click.option(
    "--username",
    help="username for login",
)
@click.option(
    "--password",
    help="password for login",
)
@click.option(
    "--domain",
    help="domain for login",
)
@click.option(
    "--title",
    help="title for article collection",
)
@click.option(
    "--subtitle",
    help="subtitle for article collection",
)
@click.option(
    "--editor",
    help="editor for article collection",
)
@click.option(
    "--script-extension",
    default=".php",
    help="script extension for PHP scripts (default: .php)",
)
@click.argument("args", nargs=-1)
def main(
    output,
    posturl,
    getposturl,
    keep_tmpfiles,
    status_file,
    config,
    imagesize,
    metabook,
    collectionpage,
    noimages,
    logfile,
    username,
    password,
    domain,
    title,
    subtitle,
    editor,
    script_extension,
    args,
):
    """Build a zip file from Wikipedia articles."""
    # Setup logging
    setup_console_logging(level=logging.INFO, stream=sys.stderr)
    log.info(
        f"starting mw-zip with log level {logging.getLevelName(log.getEffectiveLevel())}"
    )

    # Parse and validate input
    OptionsValidator.validate_imagesize(imagesize)
    parsed_metabook = MetabookParser.parse(metabook)
    parsed_metabook = MetabookParser.add_articles(parsed_metabook, args)

    # Validate options
    OptionsValidator.validate_output_options(output, posturl, getposturl)
    OptionsValidator.validate_content_options(parsed_metabook, collectionpage)

    # Create configuration
    build_config = BuildConfig(
        output=output,
        posturl=posturl,
        getposturl=getposturl,
        keep_tmpfiles=keep_tmpfiles,
        status_file=status_file,
        config=config,
        imagesize=imagesize,
        metabook=parsed_metabook,
        collectionpage=collectionpage,
        noimages=noimages,
        logfile=logfile,
        username=username,
        password=password,
        domain=domain,
        title=title,
        subtitle=subtitle,
        editor=editor,
        script_extension=script_extension,
    )

    # Build
    pod_client = PodClientFactory.create_client(posturl, getposturl)
    builder = ZipBuilder(build_config)
    result = builder.build(pod_client)

    if not result.success:
        raise result.error


if __name__ == "__main__":
    main()
