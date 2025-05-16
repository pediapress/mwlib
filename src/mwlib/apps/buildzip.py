# Copyright (c) 2007-2023 PediaPress GmbH
# See README.md for additional licensing information.

"""mz-zip - installed via setuptools' entry_points"""

import contextlib
import logging
import os
import shutil
import sys
import tempfile
import time
import webbrowser
import zipfile

import click

from mwlib.apps.make_nuwiki import make_nuwiki
from mwlib.apps.utils import create_zip_from_wiki_env, make_wiki_env_from_options
from mwlib.core.metabook import Collection
from mwlib.network.podclient import PODClient, podclient_from_serviceurl
from mwlib.utils import conf, linuxmem, unorganized
from mwlib.utils import myjson as json
from mwlib.utils.log import setup_console_logging

log = logging.getLogger(__name__)

USE_HELP_TEXT = "Use --help for usage information."


def _walk(root):
    retval = []
    for dirpath, _, files in os.walk(root):
        retval.extend(
            [os.path.normpath(os.path.join(dirpath, filepath)) for filepath in files]
        )
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
        zip_file.write(i, i[len(dirname) + 1 :])
    zip_file.close()

def make_zip(
    wiki_options=None,
    metabook=None,
    pod_client=None,
    status=None,
):
    output = wiki_options.get("output")
    dir_path = os.path.dirname(output)
    tmpdir = tempfile.mkdtemp(dir=dir_path) if output else tempfile.mkdtemp()

    try:
        fsdir = os.path.join(tmpdir, "nuwiki")
        log.info("creating nuwiki in %r" % fsdir)
        make_nuwiki(
            fsdir=fsdir,
            metabook=metabook,
            wiki_options=wiki_options,
            pod_client=pod_client,
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
        if pod_client:
            status(status="uploading", progress=0)
            pod_client.post_zipfile(filename)

        return filename

    finally:
        keep_tmpfiles = wiki_options.get("keep_tmpfiles")
        if not keep_tmpfiles:
            log.info("removing tmpdir %r" % tmpdir)
            shutil.rmtree(tmpdir, ignore_errors=True)
        else:
            log.info("keeping tmpdir %r" % tmpdir)

        if sys.platform in ("linux2", "linux3"):
            linuxmem.report()


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
    default=1200,
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
    setup_console_logging(level=logging.INFO, stream=sys.stderr)
    level = logging.getLevelName(log.getEffectiveLevel())
    log.info(f"starting mw-zip with log level {level}")
    if metabook:
        if "{" in metabook and "}" in metabook:
            metabook = json.loads(metabook)
        else:
            with open(metabook, encoding="utf-8") as file_path:
                metabook = json.load(file_path)
    for title in args:
        if metabook is None:
            metabook = Collection()
        metabook.append_article(title)
    try:
        imagesize = int(imagesize)
        if imagesize <= 0:
            raise ValueError()
    except ValueError:
        raise click.ClickException("Argument for --imagesize must be an integer > 0.")

    conf.readrc()
    if metabook is None and collectionpage is None:
        raise click.ClickException(
            "Neither --metabook nor, --collectionpage or arguments specified.\n"
            + USE_HELP_TEXT
        )

    pod_client = _init_pod_client(posturl, getposturl, output)

    filename = None
    status = None
    wiki_options = {
        "output": output,
        "posturl": posturl,
        "getposturl": getposturl,
        "keep_tmpfiles": keep_tmpfiles,
        "status_file": status_file,
        "config": config,
        "imagesize": imagesize,
        "collectionpage": collectionpage,
        "noimages": noimages,
        "logfile": logfile,
        "username": username,
        "password": password,
        "domain": domain,
        "title": title,
        "subtitle": subtitle,
        "editor": editor,
        "script_extension": script_extension,
        "metabook": metabook,
    }
    try:
        env = make_wiki_env_from_options(
            metabook=metabook,
            wiki_options=wiki_options,
        )
        status = create_zip_from_wiki_env(env, pod_client, wiki_options, make_zip)

    except Exception:
        if status:
            status(status="error")
        raise
    finally:
        if output is None and filename:
            log.info("removing %r" % filename)
            unorganized.safe_unlink(filename)


def _init_pod_client(posturl, getposturl, output):
    if posturl and getposturl:
        raise click.ClickException(
            "Specify either --posturl or --getposturl.\n" + USE_HELP_TEXT
        )
    if not posturl and not getposturl and not output:
        raise click.ClickException(
            "Neither --output, nor --posturl or --getposturl specified.\n"
            + USE_HELP_TEXT
        )
    if posturl:
        pod_client = PODClient(posturl)
    elif getposturl:
        if getposturl > 1:
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
