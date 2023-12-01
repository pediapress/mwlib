#! /usr/bin/env python

# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

import logging
import sys
import time

import six

from mwlib.configuration import conf

logging.basicConfig(format="%(asctime)-15s %(levelname)s %(name)s: %(message)s")
root_logger = logging.getLogger()
root_logger.setLevel(conf.get("logging", "log_level", "INFO", str))

# silence some loggers
logging.getLogger("PIL").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)


class Stdout:
    """late-bound sys.stdout"""

    def write(self, msg):
        sys.stdout.write(msg)

    def flush(self):
        sys.stdout.flush()


class Stderr:
    """late-bound sys.stderr"""

    def write(self, msg):
        sys.stderr.write(msg)

    def flush(self):
        sys.stderr.flush()


class Log:
    logfile = Stderr()
    timestamp_fmt = "%Y-%m-%dT%H:%M:%S"

    def __init__(self, prefix=None, timestamps=True):
        self.timestamps = timestamps
        if prefix is None:
            self._prefix = []
        else:
            if isinstance(prefix, six.string_types):
                self._prefix = [prefix]
            else:
                self._prefix = prefix

    def __getattr__(self, name):
        return Log([self, name], timestamps=self.timestamps)

    def __nonzero__(self):
        return bool(self._prefix)

    def __str__(self):
        return ".".join(str(x) for x in self._prefix if x)

    def __call__(self, msg, *args):
        if not self.logfile:
            return

        if not isinstance(msg, str):
            msg = repr(msg)

        if args:
            msg = " ".join([msg] + [repr(element) for element in args])

        log_entry = ""
        if self.timestamps:
            log_entry = f"{time.strftime(self.timestamp_fmt)} "
        log_entry += "{} >> {}\n".format(
            ".".join(str(element) for element in self._prefix if element), msg
        )
        self.logfile.write(log_entry)


class Colors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


logging.basicConfig(
    format=f"%(asctime)-15s %(levelname)s {Colors.OKBLUE}%(name)s{Colors.ENDC}: %(message)s"
)
root_logger = logging.getLogger()
root_logger.setLevel("INFO")
