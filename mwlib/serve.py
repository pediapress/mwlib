#! /usr/bin/env python

"""WSGI server interface to mw-render and mw-zip/mw-post"""

import sys, os, time, re, shutil, StringIO, errno
from hashlib import md5

from mwlib import myjson as json
from mwlib import log, _version
from mwlib.metabook import calc_checksum

log = log.Log('mwlib.serve')
collection_id_rex = re.compile(r'^[a-z0-9]{16}$')


def make_collection_id(data):
    sio = StringIO.StringIO()
    for key in (
        _version.version,
        'base_url',
        'script_extension',
        'login_credentials',
    ):
        sio.write(repr(data.get(key)))
    mb = data.get('metabook')
    if mb:
        if isinstance(mb, str):
            mb = unicode(mb, 'utf-8')
        mbobj = json.loads(mb)
        sio.write(calc_checksum(mbobj))
        num_articles = len(list(mbobj.articles()))
        sys.stdout.write("new-collection %s\t%r\t%r\n" % (num_articles, data.get("base_url"), data.get("writer")))

    return md5(sio.getvalue()).hexdigest()[:16]


def get_collection_dirs(cache_dir):
    """Generator yielding full paths of collection directories"""

    for dirpath, dirnames, filenames in os.walk(cache_dir):
        new_dirnames = []
        for d in dirnames:
            if collection_id_rex.match(d):
                yield os.path.join(dirpath, d)
            else:
                new_dirnames.append(d)
        dirnames[:] = new_dirnames


def _path_contains_entry_older_than(path, ts):
    for fn in os.listdir(path):
        if os.stat(os.path.join(path, fn)).st_mtime < ts:
            return True
    return False


def _find_collection_dirs_to_purge(collection_dirs, ts):
    for path in collection_dirs:
        try:
            if _path_contains_entry_older_than(path, ts):
                yield path
        except OSError, err:
            if err.errno != errno.ENOENT:
                log.ERROR("error while examining %r: %s" % (path, err))


def _rmtree(path):
    try:
        shutil.rmtree(path)
    except OSError, exc:
        if exc.errno != errno.ENOENT:
            log.ERROR('could not remove directory %r: %s' % (path, exc))


def purge_cache(max_age, cache_dir):
    """Remove all subdirectories of cache_dir whose mtime is before now-max_age

    @param max_age: max age of directories in seconds
    @type max_age: int

    @param cache_dir: cache directory
    @type cache_dir: basestring
    """

    for path in _find_collection_dirs_to_purge(get_collection_dirs(cache_dir), time.time() - max_age):
        _rmtree(path)
