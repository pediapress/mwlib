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

from gevent import monkey

from mwlib import conf, utils
from mwlib.options import OptionParser
from mwlib.podclient import PODClient, podclient_from_serviceurl
from mwlib.status import Status


def _walk(root):
    retval = []
    for dirpath, dirnames, files in os.walk(root):
        # retval.extend([os.path.normpath(os.path.join(dirpath, x))+"/" for x in dirnames])
        retval.extend([os.path.normpath(os.path.join(dirpath, x)) for x in files])
    retval = sorted([x.replace("\\", "/") for x in retval])
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
    zf = zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED)
    for i in _walk(dirname):
        if skip_ext and os.path.splitext(i)[1] == skip_ext:
            continue
        zf.write(i, i[len(dirname) + 1 :])
    zf.close()


def make_zip(output=None, options=None, metabook=None, podclient=None, status=None):
    tmpdir = (
        tempfile.mkdtemp(dir=os.path.dirname(output)) if output else tempfile.mkdtemp()
    )

    try:
        fsdir = os.path.join(tmpdir, "nuwiki")
        print("creating nuwiki in %r" % fsdir)
        from mwlib.apps.make_nuwiki import make_nuwiki

        make_nuwiki(
            fsdir,
            metabook=metabook,
            options=options,
            podclient=podclient,
            status=status,
        )

        if output:
            fd, filename = tempfile.mkstemp(suffix=".zip", dir=os.path.dirname(output))
        else:
            fd, filename = tempfile.mkstemp(suffix=".zip")
        os.close(fd)
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
    monkey.patch_all(thread=False)

    parser = OptionParser()
    parser.add_option("-o", "--output", help="write output to OUTPUT")
    parser.add_option("-p", "--posturl", help="http post to POSTURL (directly)")
    parser.add_option(
        "-g",
        "--getposturl",
        help="get POST URL from PediaPress.com, open upload page in webbrowser",
        action="count",
    )
    parser.add_option(
        "--keep-tmpfiles",
        action="store_true",
        default=False,
        help="don't remove  temporary files like images",
    )

    parser.add_option(
        "-s", "--status-file", help="write status/progress info to this file"
    )

    options, args = parser.parse_args()
    conf.readrc()
    use_help = "Use --help for usage information."

    if parser.metabook is None and options.collectionpage is None:
        parser.error(
            "Neither --metabook nor, --collectionpage or arguments specified.\n"
            + use_help
        )
    pod_client = _init_pod_client(options, parser, use_help)

    filename = None
    status = None
    try:
        env = parser.makewiki()
        if not env.metabook:
            raise ValueError("no metabook")

        status = Status(
            options.status_file, podclient=pod_client, progress_range=(1, 90)
        )
        status(progress=0)
        output = options.output

        make_zip(output, options, env.metabook, podclient=pod_client, status=status)

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
