# Copyright (c) 2007-2023 PediaPress GmbH
# See README.md for additional licensing information.

"""mz-zip - create nuwiki zip files"""

import contextlib
import os
import shutil
import sys
import tempfile
import time
import webbrowser
import zipfile
from pathlib import Path

from mwlib.podclient import PODClient, podclient_from_serviceurl

from .utils import build_parser, create_nuwiki, create_zip_from_wiki_env


def walk_directory(root: Path):
    return sorted(
        str(path).replace("\\", "/") for path in root.rglob("*") if path.is_file()
    )


def zip_directory(dirname: str, output: str = None, skip_ext: str = None):
    dirname = Path(dirname).resolve()
    if not output:
        output = dirname.with_suffix(".zip")

    output = Path(output).resolve()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        for filepath in walk_directory(dirname):
            if skip_ext and Path(filepath).suffix == skip_ext:
                continue
            zip_file.write(filepath, Path(filepath).relative_to(dirname))

    return output


def make_zip(output=None, options=None, metabook=None, podclient=None, status=None):
    with tempfile.TemporaryDirectory(dir=output and Path(output).parent) as tmpdir:
        tmpdir = Path(tmpdir)
        fsdir = tmpdir / "nuwiki"
        create_nuwiki(
            fsdir,
            options=options,
            metabook=metabook,
            podclient=podclient,
            status=status,
        )

        zip_path = zip_directory(fsdir, output)
        if podclient:
            status(status="uploading", progress=0)
            podclient.post_zipfile(str(zip_path))

        if options.keep_tmpfiles:
            print(f"keeping tmpdir {tmpdir}")
        else:
            print(f"removing tmpdir {tmpdir}")
            shutil.rmtree(tmpdir, ignore_errors=True)

        if sys.platform.startswith("linux"):
            from mwlib import linuxmem

            linuxmem.report()

            return zip_path


def main():
    parser, options, use_help = build_parser()
    pod_client = _init_pod_client(options, parser, use_help)

    try:
        status = create_zip_from_wiki_env(parser, pod_client, options, make_zip)
    except Exception:
        if status:
            status(status="error")
        raise


def _init_pod_client(options, parser, use_help):
    if options.posturl and options.getposturl:
        parser.error("Specify either --posturl or --getposturl.\n" + use_help)
    if not options.posturl and not options.getposturl and not options.output:
        parser.error(
            "Neither --output, nor --posturl or --getposturl specified.\n" + use_help
        )
    if options.posturl:
        pod_client = PODClient(options.posturl)
    elif options.getposturl:
        if options.getposturl > 1:
            service_url = "https://test.pediapress.com/api/collections/"
        else:
            service_url = "https://pediapress.com/api/collections/"

        pod_client = podclient_from_serviceurl(service_url)
        pid = os.fork()
        if not pid:
            try:
                webbrowser.open(pod_client.redirecturl)
            finally:
                os._exit(os.EX_OK)  # pylint: disable=W0212

        time.sleep(1)
        with contextlib.suppress(OSError):
            os.kill(pid, 9)
    else:
        pod_client = None
    return pod_client


if __name__ == "__main__":
    main()
