#! /usr/bin/env python

"""WSGI server interface to mw-render and mw-zip/mw-post"""

import sys, os, time, re, shutil, StringIO
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
        'template_blacklist',
        'template_exclusion_category',
        'print_template_prefix',
        'print_template_pattern',
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
        for d in dirnames:
            if collection_id_rex.match(d):
                yield os.path.join(dirpath, d)


def purge_cache(max_age, cache_dir):
    """Remove all subdirectories of cache_dir whose mtime is before now-max_age

    @param max_age: max age of directories in seconds
    @type max_age: int

    @param cache_dir: cache directory
    @type cache_dir: basestring
    """

    now = time.time()
    for path in get_collection_dirs(cache_dir):
        for fn in os.listdir(path):
            if now - os.stat(os.path.join(path, fn)).st_mtime > max_age:
                break
        else:
            continue
        try:
            shutil.rmtree(path)
        except Exception, exc:
            log.ERROR('could not remove directory %r: %s' % (path, exc))
