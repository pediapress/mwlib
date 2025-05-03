"""WSGI server interface to mw-render and mw-zip/mw-post"""

import errno
import logging
import os
import re
import shutil
import sys
import time
from hashlib import sha256
from io import StringIO

from mwlib.core.metabook import calc_checksum
from mwlib.utils import _version
from mwlib.utils import myjson as json

log = logging.getLogger('mwlib.serve')
collection_id_rex = re.compile(r'^[a-z0-9]{16}$')


def make_collection_id(data):
    sio = StringIO()
    for key in (
            _version.version,
        'base_url',
        'script_extension',
        'login_credentials',
    ):
        sio.write(repr(data.get(key)))
    meta_book = data.get('metabook')
    if meta_book:
        mbobj = json.loads(meta_book)
        sio.write(calc_checksum(mbobj))
        num_articles = len(list(mbobj.articles()))
        base_url = data.get('base_url')
        writer = data.get('writer')
        sys.stdout.write(
            f"new-collection {num_articles}\t{base_url}\t{writer}\n")

    return sha256(sio.getvalue().encode()).hexdigest()[:16]


def get_collection_dirs(cache_dir):
    """Generator yielding full paths of collection directories"""

    for dirpath, dirnames, _ in os.walk(cache_dir):
        new_dirnames = []
        for directory in dirnames:
            if collection_id_rex.match(directory):
                yield os.path.join(dirpath, directory)
            else:
                new_dirnames.append(directory)
        dirnames[:] = new_dirnames


def _path_contains_entry_older_than(path, time_stamp):
    return any(os.stat(
        os.path.join(path, fn)).st_mtime < time_stamp for fn in os.listdir(path))


def _find_collection_dirs_to_purge(collection_dirs, time_stamp):
    for path in collection_dirs:
        try:
            if _path_contains_entry_older_than(path, time_stamp):
                yield path
        except OSError as err:
            if err.errno != errno.ENOENT:
                log.error(f"error while examining {path!r}: {err}")


def _rmtree(path):
    try:
        shutil.rmtree(path)
    except OSError as exc:
        if exc.errno != errno.ENOENT:
            log.error(f'could not remove directory {path!r}: {exc}')


def purge_cache(max_age, cache_dir):
    """Remove all subdirectories of cache_dir whose mtime is before now-max_age

    @param max_age: max age of directories in seconds
    @type max_age: int

    @param cache_dir: cache directory
    @type cache_dir: str
    """

    for path in _find_collection_dirs_to_purge(
            get_collection_dirs(cache_dir), time.time() - max_age):
        _rmtree(path)
