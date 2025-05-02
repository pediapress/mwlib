# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

"""mw-render -- installed via setuptools' entry_points"""

import errno
import logging
import os
import shutil
import sys
import tempfile
import time
import traceback
from importlib.metadata import entry_points

import click

from mwlib.core import nuwiki, wiki
from mwlib.apps.buildzip import make_zip
from mwlib.apps.utils import make_wiki_env_from_options
from mwlib.exceptions.mwlib_exceptions import RenderException
from mwlib.localization import _locale
from mwlib.utils.status import Status
from mwlib.utils import unorganized, conf
from mwlib.utils.log import setup_console_logging
from mwlib.utils.unorganized import start_logging
from mwlib.rendering.writerbase import WriterError

logger = logging.getLogger(__name__)
USE_HELP_TEXT = "Use --help for usage information."


def init_tmp_cleaner():
    tempfile.tempdir = tempfile.mkdtemp(prefix="tmp-%s" % os.path.basename(sys.argv[0]))
    os.environ["TMP"] = os.environ["TEMP"] = os.environ["TMPDIR"] = tempfile.tempdir
    ppid = os.getpid()
    try:
        pid = os.fork()
    except BaseException:
        shutil.rmtree(tempfile.tempdir)
        raise

    if pid == 0:
        os.closerange(0, 3)
        os.setpgrp()
        while True:
            if os.getppid() != ppid:
                try:
                    shutil.rmtree(tempfile.tempdir)
                finally:
                    os._exit(0)
            time.sleep(1)



def finish_render(writer, options, zip_filename, status):
    kwargs = {}
    if hasattr(writer, "content_type"):
        kwargs["content_type"] = writer.content_type
    if hasattr(writer, "file_extension"):
        kwargs["file_extension"] = writer.file_extension
    status(status="finished", progress=100, **kwargs)
    keep_zip = options.get("keep_zip")
    if keep_zip is None and zip_filename is not None:
        unorganized.safe_unlink(zip_filename)

def write_traceback(options, exc, status):
    status(status="error")
    error_file = options.get("error_file")
    if error_file:
        file_descriptor, tmpfile = tempfile.mkstemp(
            dir=os.path.dirname(error_file)
        )
        error_file = os.fdopen(file_descriptor, "wb")
        if isinstance(exc, WriterError):
            error_file.write(str(exc))
        else:
            error_file.write("traceback\n")
            traceback.print_exc(file=error_file)
        error_file.write(f"sys.argv={unorganized.garble_password(sys.argv)!r}\n")
        error_file.close()
        os.rename(tmpfile, error_file)

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
@click.option(
    "-w",
    "--writer",
    help="use writer backend WRITER",
)
@click.option(
    "-y",
    "--writer-options",
    help='";"-separated list of additional writer-specific options',
)
@click.option(
    "--list-writers",
    is_flag=True,
    help="list available writers and exit",
)
@click.option(
    "--writer-info",
    help="list information about given WRITER and exit",
)
@click.option(
    "--keep-zip",
    help="write ZIP file to FILENAME",
)
@click.option(
    "--keep-tmpfiles",
    is_flag=True,
    default=False,
    help="don't remove  temporary files like images",
)
@click.option(
    "-L",
    "--language",
    help="use translated strings in LANGUAGE",
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
    writer,
    writer_options,
    list_writers,
    writer_info,
    keep_zip,
    language,
    args,
):
    conf.readrc()
    if logfile:
        start_logging(logfile)
    setup_console_logging(level="INFO", stream=sys.stderr)
    options = {
        "list_writers": list_writers,
        "writer_info": writer_info,
        "output": output,
        "posturl": posturl,
        "getposturl": getposturl,
        "keep_tmpfiles": keep_tmpfiles,
        "status_file": status_file,
        "config": config,
        "imagesize": imagesize,
        "metabook": metabook,
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
        "writer": writer,
        "writer_options": writer_options,
        "keep_zip": keep_zip,
        "language": language,
        "args": args,
    }
    writer, writer_options = get_writer_from_options(
        options
    )
    init_tmp_cleaner()
    status = Status(status_file, progress_range=(1, 33))
    status(progress=0)
    env = None
    try:
        env, status, zip_filename = get_environment(options)
        try:
            _locale.set_locale_from_lang(env.wiki.siteinfo["general"]["lang"])
        except Exception as err:
            print("Error: could not set locale", err)
        basename = os.path.basename(output)
        ext = "." + basename.rsplit(".", 1)[-1] if "." in basename else ""
        file_descriptor, tmpout = tempfile.mkstemp(
            dir=os.path.dirname(output), suffix=ext
        )
        os.close(file_descriptor)
        writer(env, output=tmpout, status_callback=status, **writer_options)
        os.rename(tmpout, output)
        finish_render(writer, options, zip_filename, status)
    except Exception as exc:
        write_traceback(options, exc, status)
        raise RenderException("ERROR: %s" % exc) from exc
    finally:
        if env is not None and env.images is not None:
            try:
                if not keep_tmpfiles:
                    env.images.clear()
            except OSError as exc:
                if exc.errno != errno.ENOENT:
                    print(
                        "ERROR: Could not remove temporary images: %s" % exc,
                        exc.errno,
                    )

def get_environment(options):
    env = make_wiki_env_from_options(None, options)

    if isinstance(env.wiki, nuwiki.NuWiki | nuwiki.Adapt) or isinstance(
        env, wiki.MultiEnvironment
    ):
        status_file = options.get("status_file")
        status = Status(status_file, progress_range=(0, 100))
        return env, status, None
    keep_zip = options.get("keep_zip")
    zip_filename = make_zip(
        output=keep_zip,
        wiki_options=options,
        metabook=env.metabook,
        status=status,
    )
    if env.images:
        try:
            env.images.clear()
        except OSError as err:
            if err.errno != errno.ENOENT:
                raise
    env = wiki.make_wiki(zip_filename)
    status = Status(options.status_file, progress_range=(34, 100))
    return env, status, zip_filename

def show_writer_info(name):
    writer = load_writer(name)
    if hasattr(writer, "description"):
        print("Description:\t%s" % writer.description)
    if hasattr(writer, "content_type"):
        print("Content-Type:\t%s" % writer.content_type)
    if hasattr(writer, "file_extension"):
        print("File extension:\t%s" % writer.file_extension)
    if hasattr(writer, "options") and writer.options:
        print('Options (usable in a ";"-separated list for --writer-options):')
        for name, info in writer.options.items():
            param = info.get("param")
            if param:
                print(" {}={}:\t{}".format(name, param, info["help"]))
            else:
                print(" {}:\t{}".format(name, info["help"]))

def get_writer_from_options(options):
    if options.get("list_writers"):
        list_writers()
        return
    writer_info = options.get("writer_info")
    if writer_info:
        show_writer_info(writer_info)
        return
    output = options.get("output")
    if output is None:
        raise click.UsageError("Please specify an output file with --output.\n" + USE_HELP_TEXT)
    options['output'] = os.path.abspath(output)
    writer = options.get("writer")
    if writer is None:
        raise click.UsageError("Please specify a writer with --writer.\n" + USE_HELP_TEXT)
    writer = load_writer(writer)
    writer_options = {}
    if options.get("writer_options"):
        for wopt in options['writer_options'].split(";"):
            if "=" in wopt:
                key, value = wopt.split("=", 1)
            else:
                key, value = wopt, True
            writer_options[str(key)] = value
    language = options.get("language")
    if language:
        writer_options["lang"] = language
    options_to_remove = []
    for option in writer_options:
        if option not in getattr(writer, "options", {}):
            logger.warning("Warning: unknown writer option %r" % option)
            options_to_remove.append(option)
    for option in options_to_remove:
        del writer_options[option]
    return writer, writer_options

def load_writer(name):
    try:
        entry_point = next(
            ep for ep in entry_points().get("mwlib.writers", []) if ep.name == name
        )
    except StopIteration:
        sys.exit(
            "No such writer: %r (use --list-writers to list available writers)" % name
        )
    try:
        return entry_point.load()
    except Exception as exc:
        sys.exit(f"Could not load writer {name!r}: {exc}")


def list_writers():
    writers = set()
    for entry_point in entry_points().get("mwlib.writers", []):
        try:
            writer = entry_point.load()
            if hasattr(writer, "description"):
                description = writer.description
            else:
                description = "<no description>"
        except ImportError as exc:
            logger.exception("Could not load writer %r: %s", entry_point.name, exc)
            description = "<NOT LOADABLE: %s>" % exc
            continue
        writers.add((entry_point.name, description))
    print("Available writers:")
    for name, description in sorted(writers):
        print(f"  {name}\t{description}")
    sys.exit(0)


if __name__ == "__main__":
    main()
