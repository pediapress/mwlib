import errno
import exceptions
try:
    from hashlib import md5
except ImportError:
    from md5 import md5
import os
import sys
import tempfile
import time
import urllib2
import UserDict

from mwlib.log import Log

if urllib2.getproxies():
    log.info("using proxy %r" % urllib2.getproxies())



log = Log('mwlib.utils')


# provide all for python 2.4
try:
    from __builtin__ import all
except ImportError:
    def all(items):
        for x in items:
            if not x:
                return False
        return True

def fsescape(s):
    res = []
    for x in s:
        c = ord(x)
        if c>127: 
            res.append("~%s~" % c)
        elif c==126: # ord("~")==126
            res.append("~~")
        else:
            res.append(x)
    return "".join(res)
    
def start_logging(path):
    sys.stderr.flush()
    sys.stdout.flush()
    
    f = open(path, "a")
    fd = f.fileno()
    os.dup2(fd, 1)
    os.dup2(fd, 2)
    
    null=os.open('/dev/null', os.O_RDWR)
    os.dup2(null, 0)
    os.close(null)
        
def daemonize(dev_null=False):
    # See http://www.erlenstar.demon.co.uk/unix/faq_toc.html#TOC16
    if os.fork():   # launch child and...
        os._exit(0) # kill off parent
    os.setsid()
    if os.fork():   # launch child and...
        os._exit(0) # kill off parent again.
    os.umask(077)
    if dev_null:
        null=os.open('/dev/null', os.O_RDWR)
        for i in range(3):
            try:
                os.dup2(null, i)
            except OSError, e:
                if e.errno != errno.EBADF:
                    raise
        os.close(null)

def shell_exec(cmd):
    """Execute cmd in a subshell
    
    @param cmd: command to execute with os.system(), if given as unicode its
        converted to str using sys.getfilesystemencoding()
    @type cmd: basestring
    
    @returns: exit code of command
    @rtype: int
    """
    if isinstance(cmd, unicode):
        enc = sys.getfilesystemencoding()
        assert enc is not None, 'no filesystem encoding (set LANG)'
        cmd = cmd.encode(enc, 'ignore')
    return os.system(cmd)


def get_multipart(filename, data, name):
    """Build data in format multipart/form-data to be used to POST binary data.
    
    @param filename: filename to be used in multipart request
    @type filenaem: basestring
    
    @param data: binary data to include
    @type data: str
    
    @param name: name to be used in multipart request
    @type name: basestring
    
    @returns: tuple containing content-type and body for the request
    @rtype: (str, str)
    """
    
    if isinstance(filename, unicode):
        filename = filename.encode('utf-8', 'ignore')
    if isinstance(name, unicode):
        name = name.encode('utf-8', 'ignore')
    
    boundary = "-"*20 + ("%f" % time.time()) + "-"*20
    
    items = []
    items.append("--" + boundary)
    items.append('Content-Disposition: form-data; name="%(name)s"; filename="%(filename)s"'\
                 % {'name': name, 'filename': filename})
    items.append('Content-Type: application/octet-stream')
    items.append('')
    items.append(data)
    items.append('--' + boundary + '--')
    items.append('')
    
    body = "\r\n".join(items)
    content_type = 'multipart/form-data; boundary=%s' % boundary
    
    return content_type, body



# --------------------- CACHE for mwapidb ----------------------
"""
persists documents in tempdir

usage::

>>> from mwlib.utils import Cache, fetch_url
>>> cache = Cache()
>>> data = fetch_url(some_url, fetch_cache=cache, max_cacheable_size=5*1024*1024)
"""

cache_prefix = "%s/mwlibcache." % tempfile.gettempdir()

def fname(key):
    return cache_prefix + md5(key).hexdigest()

class Cache(UserDict.UserDict):
    def __getitem__(self, name):
        fn = fname(name)
        if os.path.exists(fn):
            return open(fn).read()
        raise exceptions.KeyError, name

    def __setitem__(self, name, value):
        fn = fname(name)
        if not os.path.exists(fn):
            return open(fn, "w").write(value)

    def __contains__(self, name):
        fn = fname(name)
        return os.path.exists(fn)

# ==============================================================================

fetch_cache = {}

def fetch_url(url, ignore_errors=False, fetch_cache=fetch_cache,
    max_cacheable_size=1024, expected_content_type=None):
    if url in fetch_cache:
        return fetch_cache[url]
    
    log.info("fetching %r" % (url,))
    opener = urllib2.build_opener()
    opener.addheaders = [('User-agent', 'mwlib')]
    try:
        result = opener.open(url)
        data = result.read()
        if expected_content_type:
            content_type = result.info().gettype()
            if content_type != expected_content_type:
                msg = 'Got content-type %r, expected %r' % (
                    content_type,
                    expected_content_type,
                )
                if ignore_errors:
                    log.warn(msg)
                else:
                    raise RuntimeError(msg)
                return None
    except urllib2.URLError, err:
        if ignore_errors:
            log.error("%s - while fetching %r" % (err, url))
            return None
        raise RuntimeError('Could not fetch %r: %s' % (url, err))
    log.info("got %r (%d Bytes)" % (url, len(data)))
    
    if len(data) < max_cacheable_size:
        fetch_cache[url] = data
    
    return data
