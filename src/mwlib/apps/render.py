# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

"""mw-render -- installed via setuptools' entry_points"""

import errno
import os
import shutil
import sys
import tempfile
import time
import traceback
from importlib.metadata import entry_points

from mwlib import nuwiki, wiki
from mwlib.apps.buildzip import make_zip
from mwlib.configuration import conf
from mwlib.exceptions.mwlib_exceptions import RenderException
from mwlib.localization import _locale
from mwlib.miscellaneous.status import Status
from mwlib.utilities import utils
from mwlib.utilities.log import root_logger
from mwlib.utilities.options import OptionParser
from mwlib.writerbase import WriterError


logger = root_logger.getChild(__name__)


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


class Main:
    zip_filename = None

    def parse_options(self):
        parser = OptionParser()
        arg = parser.add_option

        arg("-o", "--output", help="write output to OUTPUT")
        arg("-w", "--writer", help="use writer backend WRITER")
        arg(
            "-W",
            "--writer-options",
            help='";"-separated list of additional writer-specific options',
        )
        arg("-e", "--error-file", help="write errors to this file")
        arg("-s", "--status-file", help="write status/progress info to this file")
        arg("--list-writers", action="store_true", help="list available writers and exit")
        arg(
            "--writer-info",
            metavar="WRITER",
            help="list information about given WRITER and exit",
        )
        arg("--keep-zip", metavar="FILENAME", help="write ZIP file to FILENAME")
        arg(
            "--keep-tmpfiles",
            action="store_true",
            default=False,
            help="don't remove  temporary files like images",
        )
        arg("-L", "--language", help="use translated strings in LANGUAGE")

        options, args = parser.parse_args()
        return options, args, parser

    def load_writer(self, name):
        try:
            entry_point = next(
                ep for ep in entry_points().get("mwlib.writers", []) if ep.name == name
            )
        except StopIteration:
            sys.exit("No such writer: %r (use --list-writers to list available writers)" % name)
        try:
            return entry_point.load()
        except Exception as exc:
            sys.exit(f"Could not load writer {name!r}: {exc}")

    def list_writers(self):
        writers = set()
        for entry_point in entry_points().get('mwlib.writers', []):
            try:
                writer = entry_point.load()
                if hasattr(writer, "description"):
                    description = writer.description
                else:
                    description = "<no description>"
            except ImportError as exc:
                # logger.exception("Could not load writer %r: %s", entry_point.name, exc)
                description = "<NOT LOADABLE: %s>" % exc
                continue
            writers.add((entry_point.name, description))
        print("Available writers:")
        for (name, description) in sorted(writers):
            print(f"  {name}\t{description}")

        sys.exit(0)

    def show_writer_info(self, name):
        writer = self.load_writer(name)
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

    def get_environment(self):
        env = self.parser.make_wiki()
        if isinstance(env.wiki, (nuwiki.NuWiki, nuwiki.Adapt)) or isinstance(
            env, wiki.MultiEnvironment
        ):
            self.status = Status(self.options.status_file, progress_range=(0, 100))
            return env
        self.zip_filename = make_zip(
            output=self.options.keep_zip,
            options=self.options,
            metabook=env.metabook,
            status=self.status,
        )

        if env.images:
            try:
                env.images.clear()
            except OSError as err:
                if err.errno != errno.ENOENT:
                    raise

        env = wiki.make_wiki(self.zip_filename)
        self.status = Status(self.options.status_file, progress_range=(34, 100))
        return env

    def _get_writer_from_options(self, options, parser, use_help):
        if options.list_writers:
            self.list_writers()
            return

        if options.writer_info:
            self.show_writer_info(options.writer_info)
            return

        if options.output is None:
            parser.error("Please specify an output file with --output.\n" + use_help)

        options.output = os.path.abspath(options.output)

        if options.writer is None:
            parser.error("Please specify a writer with --writer.\n" + use_help)

        writer = self.load_writer(options.writer)
        writer_options = {}
        if options.writer_options:
            for wopt in options.writer_options.split(";"):
                if "=" in wopt:
                    key, value = wopt.split("=", 1)
                else:
                    key, value = wopt, True
                writer_options[str(key)] = value
        if options.language:
            writer_options["lang"] = options.language
        for option in writer_options:
            if option not in getattr(writer, "options", {}):
                print("Warning: unknown writer option %r" % option)
                del writer_options[option]

        return writer, writer_options

    def _finish_render(self, writer, options):
        kwargs = {}
        if hasattr(writer, "content_type"):
            kwargs["content_type"] = writer.content_type
        if hasattr(writer, "file_extension"):
            kwargs["file_extension"] = writer.file_extension
        self.status(status="finished", progress=100, **kwargs)
        if options.keep_zip is None and self.zip_filename is not None:
            utils.safe_unlink(self.zip_filename)

    def _write_traceback(self, options, exc):
        self.status(status="error")
        if options.error_file:
            file_descriptor, tmpfile = tempfile.mkstemp(dir=os.path.dirname(options.error_file))
            error_file = os.fdopen(file_descriptor, "wb")
            if isinstance(exc, WriterError):
                error_file.write(str(exc))
            else:
                error_file.write("traceback\n")
                traceback.print_exc(file=error_file)
            error_file.write(f"sys.argv={utils.garble_password(sys.argv)!r}\n")
            error_file.close()
            os.rename(tmpfile, options.error_file)

    def __call__(self):
        options, _, parser = self.parse_options()
        conf.readrc()

        self.parser = parser
        self.options = options

        use_help = "Use --help for usage information."

        writer, writer_options = self._get_writer_from_options(options, parser, use_help)

        init_tmp_cleaner()

        self.status = Status(options.status_file, progress_range=(1, 33))
        self.status(progress=0)

        env = None
        try:
            env = self.get_environment()

            try:
                _locale.set_locale_from_lang(env.wiki.siteinfo["general"]["lang"])
            except Exception as err:
                print("Error: could not set locale", err)

            basename = os.path.basename(options.output)
            ext = "." + basename.rsplit(".", 1)[-1] if "." in basename else ""
            file_descriptor, tmpout = tempfile.mkstemp(
                dir=os.path.dirname(options.output), suffix=ext
            )
            os.close(file_descriptor)
            writer(env, output=tmpout, status_callback=self.status, **writer_options)
            os.rename(tmpout, options.output)
            self._finish_render(writer, options)
        except Exception as exc:
            self._write_traceback(options, exc)
            raise RenderException("ERROR: %s" % exc) from exc
        finally:
            if env is not None and env.images is not None:
                try:
                    if not options.keep_tmpfiles:
                        env.images.clear()
                except OSError as exc:
                    if exc.errno != errno.ENOENT:
                        print("ERROR: Could not remove temporary images: %s" % exc, exc.errno)


def main():
    return Main()()


if __name__ == "__main__":
    main()
