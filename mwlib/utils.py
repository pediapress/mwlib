import errno
import os
import StringIO
import sys
import tempfile
import time
import urllib2
import UserDict

from mwlib.log import Log

try:
    from hashlib import md5
except ImportError:
    from md5 import md5

# provide all() for python 2.4
try:
    from __builtin__ import all
except ImportError:
    def all(iterable):
        """all(iterable) -> bool

        Return True if bool(x) is True for all values x in the iterable.
        """
        
        for x in iterable:
            if not x:
                return False
        return True

# ==============================================================================

log = Log('mwlib.utils')

# ==============================================================================

def fsescape(s):
    """Escape string to be safely used in path names
    
    @param s: some string
    @type s: basestring
    
    @returns: escaped string
    @rtype: str
    """
    
    res = []
    for x in s:
        c = ord(x)
        if c>127: 
            res.append("~%s~" % c)
        elif c==126: # ord("~")==126
            res.append("~~")
        else:
            res.append(x.encode('ascii'))
    return "".join(res)
    
# ==============================================================================

def start_logging(path, stderr_only=False):
    """Redirect all output to sys.stdout or sys.stderr to be appended to a file,
    redirect sys.stdin to /dev/null.
    
    @param path: filename of logfile
    @type path: basestring
    
    @param stderr_only: if True, only redirect stderr, not stdout & stdin
    @type stderr_only: bool
    """
    
    if not stderr_only:
        sys.stdout.flush()
    sys.stderr.flush()
    
    f = open(path, "a")
    fd = f.fileno()
    if not stderr_only:
        os.dup2(fd, 1)
    os.dup2(fd, 2)
    
    if not stderr_only:
        null = os.open(os.path.devnull, os.O_RDWR)
        os.dup2(null, 0)
        os.close(null)

# ==============================================================================

def daemonize(pid_file=None, dev_null=False):
    """Deamonize current process
    
    Note: This only works on systems that have os.fork(), i.e. it doesn't work
    on Windows.
    
    See http://www.erlenstar.demon.co.uk/unix/faq_toc.html#TOC16
    
    @param pid_file: write PID of daemon process to this file
    @type pid_file: basestring
    
    @param dev_null: if True, redirect stdin, stdout and stderr to /dev/null
    @type dev_null: bool
    """
    
    if os.fork():   # launch child and...
        os._exit(0) # ... kill off parent
    os.setsid()
    pid = os.fork() # launch child and...
    if pid:
        try:
            if pid_file is not None:
                open(pid_file, 'w').write('%d\n' % pid)
        finally:
            os._exit(0) # ... kill off parent again.
    os.umask(077)
    if dev_null:
        null = os.open(os.path.devnull, os.O_RDWR)
        for i in range(3):
            try:
                os.dup2(null, i)
            except OSError, e:
                if e.errno != errno.EBADF:
                    raise
        os.close(null)

# ==============================================================================

def shell_exec(cmd):
    """Execute cmd in a subshell
    
    @param cmd: command to execute with os.system(), if given as unicode it's
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

# ==============================================================================

def get_multipart(filename, data, name):
    """Build data in format multipart/form-data to be used to POST binary data
    
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

# ==============================================================================


class PersistedDict(UserDict.UserDict):
    """Subclass of dict that persists its contents in tempdir. Every value is
    stored in a file whose filename is based on the md5 sum of the key. All
    values must be strings!
    
    Example usage with fetch_url()::
    
        from mwlib.utils import Cache, fetch_url
        cache = Cache()
        data = fetch_url(some_url, fetch_cache=cache, max_cacheable_size=5*1024*1024)
    """
    
    cache_dir = os.path.join(tempfile.gettempdir(), 'mwlib-cache')
    
    def __init__(self, max_cacheable_size=1024*1024, *args, **kwargs):
        """
        @param max_cacheable_size: max. size in bytes for each cache value
        @type max_cacheable_size: int
        """
        
        super(PersistedDict, self).__init__(*args, **kwargs)
        self.max_cacheable_size = max_cacheable_size
        ensure_dir(self.cache_dir)
    
    def __getitem__(self, name):
        fn = self.fname(name)
        if os.path.exists(fn):
            return open(fn, 'rb').read()
        raise KeyError(name)
    
    def __setitem__(self, name, value):
        assert isinstance(value, str), 'only string values are supported'
        
        fn = self.fname(name)
        if not os.path.exists(fn):
            return open(fn, 'wb').write(value)
    
    def __contains__(self, name):
        fn = self.fname(name)
        return os.path.exists(fn)
    
    def fname(self, key):
        return os.path.join(self.cache_dir, md5(key).hexdigest())
    

# ==============================================================================

fetch_cache = {}

def fetch_url(url, ignore_errors=False, fetch_cache=fetch_cache,
    max_cacheable_size=1024, expected_content_type=None, opener=None):
    """Fetch given URL via HTTP
    
    @param ignore_errors: if True, log but otherwise ignore errors, return None
    @type ignore_errors: bool
    
    @param fetch_cache: dictionary used as cache, with urls as keys and fetched
        data as values
    @type fetch_cache: dict
    
    @param max_cacheable_size: max. size for responses to be cached
    @type max_cacheable_size: int
    
    @param expected_content_type: if given, raise (or log) an error if the
        content-type of the reponse does not mathc
    @type expected_content_type: str
    
    @param opener: if give, use this opener instead of instantiating a new one
    @type opener: L{urllib2.URLOpenerDirector}
    
    @returns: fetched reponse or None
    @rtype: str
    """
    
    if url in fetch_cache:
        return fetch_cache[url]
    
    log.info("fetching %r" % (url,))
    if opener is None:
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
    
    if hasattr(fetch_cache, 'max_cacheable_size'):
        max_cacheable_size = max(fetch_cache.max_cacheable_size, max_cacheable_size)
    if len(data) <= max_cacheable_size:
        fetch_cache[url] = data
    
    return data

def uid(max_length=10):
    """Generate a unique identifier of given maximum length
    
    @parma max_length: maximum length of identifier
    @type max_length: int
    
    @returns: unique identifier
    @rtype: str
    """
    
    f = StringIO.StringIO()
    print >>f, "%.20f" % time.time()
    print >>f, os.times()
    print >>f, os.getpid()
    m = md5(f.getvalue())
    return m.hexdigest()[:max_length]

def ensure_dir(d):
    """If directory d does not exist, create it
    
    @param d: name of an existing or not-yet-existing directory
    @type d: basestring
    
    @returns: d
    @rtype: basestring
    """
    
    if not os.path.isdir(d):
        log.info('mkdir -r %r' % d)
        os.makedirs(d)
    return d

