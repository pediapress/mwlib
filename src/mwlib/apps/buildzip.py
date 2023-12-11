# Copyright (c) 2007-2023 PediaPress GmbH
# See README.md for additional licensing information.

"""mz-zip - installed via setuptools' entry_points"""

import contextlib
import os
import shutil
import sys
import tempfile
import time
import webbrowser
import zipfile

from mwlib.apps.utils import build_parser, create_nuwiki, create_zip_from_wiki_env
from mwlib.networking.net.podclient import PODClient, podclient_from_serviceurl
from mwlib.utilities import utils


def _walk(root):
    retval = []
    for dirpath, _, files in os.walk(root):
        retval.extend([os.path.normpath(os.path.join(dirpath, filepath)) for filepath in files])
    retval = sorted([ret.replace("\\", "/") for ret in retval])
    return retval


def zip_dir(dirname, output=None, skip_ext=None):
    """recursively zip directory and write output to zipfile.
    @param dirname: directory to zip
    @param output: name of zip file that gets written
    @param skip_ext: skip files with the specified extension
    """
    if not output:
        output = dirname + ".zip"

    output = os.path.abspath(output)
    zip_file = zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED)
    for i in _walk(dirname):
        if skip_ext and os.path.splitext(i)[1] == skip_ext:
            continue
        zip_file.write(i, i[len(dirname) + 1:])
    zip_file.close()


def make_zip(output=None, options=None, metabook=None, podclient=None, status=None):
    dir_path = os.path.dirname(output)
    tmpdir = tempfile.mkdtemp(dir=dir_path) if output else tempfile.mkdtemp()

    try:
        fsdir = os.path.join(tmpdir, "nuwiki")
        create_nuwiki(
            fsdir,
            options=options,
            metabook=metabook,
            podclient=podclient,
            status=status,
        )

        if output:
            file_descriptor, filename = tempfile.mkstemp(
                suffix=".zip", dir=os.path.dirname(output)
            )
        else:
            file_descriptor, filename = tempfile.mkstemp(suffix=".zip")
        os.close(file_descriptor)
        zip_dir(fsdir, filename)
        if output:
            os.rename(filename, output)
            filename = output

        if podclient:
            status(status="uploading", progress=0)
            podclient.post_zipfile(filename)

        return filename

    finally:
        if not options.keep_tmpfiles:
            print("removing tmpdir %r" % tmpdir)
            shutil.rmtree(tmpdir, ignore_errors=True)
        else:
            print("keeping tmpdir %r" % tmpdir)

        if sys.platform in ("linux2", "linux3"):
            from mwlib import linuxmem

            linuxmem.report()


def main():
    parser, options, use_help = build_parser()

    pod_client = _init_pod_client(options, parser, use_help)

    filename = None
    status = None
    try:
        status = create_zip_from_wiki_env(parser, pod_client, options, make_zip)
    except Exception:
        if status:
            status(status="error")
        raise
    finally:
        if options.output is None and filename:
            print("removing %r" % filename)
            utils.safe_unlink(filename)


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
