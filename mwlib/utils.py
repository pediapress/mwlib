from email.mime.text import MIMEText
from email.utils import make_msgid, formatdate
    
import errno
import os
import pprint
import re
import smtplib
import socket
import StringIO
import sys
import tempfile
import time
import traceback
import urllib
import urllib2
import urlparse
import UserDict

from mwlib.log import Log

from hashlib import md5

# provide all() for python 2.4
all = all

# ==============================================================================

log = Log('mwlib.utils')

# ==============================================================================

def get_print_template_maker(pattern):
    assert "$1" in pattern, 'pattern %r does not contain "$1"' % pattern
    
    def make_print_template(title):
        if ':' in title:
            p, s = title.split(":", 1)
            s = pattern.replace("$1", s)
            return '%s:%s' % (p, s)
        else:
            return pattern.replace("$1", title)
        
    return make_print_template

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
        if c>127 or c==47 or c==92: # 47==slash, 92==backslash
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

def daemonize(dev_null=False):
    """Deamonize current process
    
    Note: This only works on systems that have os.fork(), i.e. it doesn't work
    on Windows.
    
    See http://www.erlenstar.demon.co.uk/unix/faq_toc.html#TOC16
    
    @param dev_null: if True, redirect stdin, stdout and stderr to /dev/null
    @type dev_null: bool
    """
    
    if os.fork():   # launch child and...
        os._exit(0) # ... kill off parent
    os.setsid()
    pid = os.fork() # launch child and...
    if pid:
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
    
    
    def __init__(self, max_cacheable_size=1024*1024, *args, **kwargs):
        """
        @param max_cacheable_size: max. size in bytes for each cache value
        @type max_cacheable_size: int
        """
        
        #super(PersistedDict, self).__init__(*args, **kwargs)
        UserDict.UserDict.__init__(self, *args, **kwargs)
        self.max_cacheable_size = max_cacheable_size
        self.cache_dir = os.path.join(tempfile.gettempdir(), 'mwlib-cache')
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

def safe_unlink(filename):
    """Never failing os.unlink()"""
    
    try:
        os.unlink(filename)
    except Exception, exc:
        log.warn('Could not remove file %r: %s' % (filename, exc))

# ==============================================================================

fetch_cache = {}

def fetch_url(url, ignore_errors=False, fetch_cache=fetch_cache,
    max_cacheable_size=1024, expected_content_type=None, opener=None,
    output_filename=None, post_data=None, timeout=10.0):
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
    
    @param output_filename: write response to given file
    @type output_filename: basestring
    
    @param post_data: if given use POST request
    @type post_data: dict
    
    @param timeout: timeout in seconds
    @type timeout: float
    
    @returns: fetched response or True if filename was given; None when
        ignore_errors is True, and the request failed
    @rtype: str
    """

    if not post_data and url in fetch_cache:
        return fetch_cache[url]
    
    log.info("fetching %r" % (url,))
    start_time = time.time()
    socket.setdefaulttimeout(timeout)
    if opener is None:
        opener = urllib2.build_opener()
        opener.addheaders = [('User-agent', 'mwlib')]
    try:
        if post_data:
            post_data = urllib.urlencode(post_data)
        result = opener.open(url, post_data)
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
    #log.info("got %r (%dB in %.2fs)" % (url, len(data), time.time() - start_time))
    
    if hasattr(fetch_cache, 'max_cacheable_size'):
        max_cacheable_size = max(fetch_cache.max_cacheable_size, max_cacheable_size)
    if len(data) <= max_cacheable_size:
        fetch_cache[url] = data
    
    if output_filename:
        open(output_filename, 'wb').write(data)
        return True
    else:
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
        os.makedirs(d)
    return d


# ==============================================================================

def send_mail(from_email, to_emails, subject, body, headers=None, host='mail', port=25):
    """Send an email via SMTP
    
    @param from_email: email address for From: header
    @type from_email: str
    
    @param to_emails: sequence of email addresses for To: header
    @type to_email: [str]
    
    @param subject: text for Subject: header
    @type subject: unicode
    
    @param body: text for message body
    @type body: unicode
    
    @param host: mail server host
    @type host: str
    
    @param port: mail server port
    @type port: int
    """
    
    connection = smtplib.SMTP(host, port)
    msg = MIMEText(body.encode('utf-8'), 'plain', 'utf-8')
    msg['Subject'] = subject.encode('utf-8')
    msg['From'] = from_email
    msg['To'] = ', '.join(to_emails)
    msg['Date'] = formatdate()
    msg['Message-ID'] = make_msgid()
    if headers is not None:
        for k, v in headers.items():
            if not isinstance(v, str):
                v = str(v)
            msg[k] = v
    connection.sendmail(from_email, to_emails, msg.as_string())
    connection.close()


# ==============================================================================

def asunicode(x):
    if not isinstance(x, basestring):
        x = repr(x)
    
    if isinstance(x, str):
        x = unicode(x, "utf-8", "replace")

    return x

def ppdict(dct):
    items = dct.items()
    items.sort()
    tmp = []
    write = tmp.append
    
    for k, v in items:
        write(u"*"+asunicode(k)+u"*")
        v = asunicode(v)
        lines = v.split("\n")
        for x in lines:
            write(" "*4+x)
        write("")
        
    return u"\n".join(tmp)

def report(system='', subject='', from_email=None, mail_recipients=None, mail_headers=None, **kw):
    log.report('system=%r subject=%r' % (system, subject))
    
    text = []
    text.append('SYSTEM: %r\n' % system)
    text.append('%s\n' % traceback.format_exc())
    try:
        fqdn = socket.getfqdn()
    except:
        fqdn = 'not available'
    text.append('CWD: %r\n' % os.getcwd())

    text.append(ppdict(kw).encode("utf-8"))
    # text.append('KEYWORDS:\n%s\n' % pprint.pformat(kw, indent=4))
    text.append('ENV:\n%s\n' % pprint.pformat(dict(os.environ), indent=4))

    text = '\n'.join(text)

    if not (from_email and mail_recipients):
        return text

    try:
        if not isinstance(subject, str):
            subject = repr(subject)
        send_mail(
            from_email,
            mail_recipients,
            'REPORT [%s]: %s' % (fqdn, subject),
            text,
            headers=mail_headers,
        )
        log.info('sent mail to %r' % mail_recipients)
    except Exception, e:
        log.ERROR('Could not send mail: %s' % e)
    return text

# ==============================================================================

def get_safe_url(url):
    if not isinstance(url, str):
        url = url.encode('utf-8')
    
    nonwhitespace_rex = re.compile(r'^\S+$')
    try:
        result = urlparse.urlsplit(url)
        scheme, netloc, path, query, fragment = result
    except Exception, exc:
        log.warn('urlparse(%r) failed: %s' % (url, exc))
        return None
    
    if not (scheme and netloc):
        log.warn('Empty scheme or netloc: %r %r' % (scheme, netloc))
        return None
    
    if not (nonwhitespace_rex.match(scheme) and nonwhitespace_rex.match(netloc)):
        log.warn('Found whitespace in scheme or netloc: %r %r' % (scheme, netloc))
        return None
    
    try:
        # catches things like path='bla " target="_blank'
        path = urllib.quote(urllib.unquote(path))
    except Exception, exc:
        log.warn('quote(unquote(%r)) failed: %s' % (path, exc))
        return None
    try:
        return urlparse.urlunsplit((scheme, netloc, path, query, fragment))
    except Exception, exc:
        log.warn('urlunparse() failed: %s' % exc)
    
# ##########################################################################

def get_nodeweight(obj):
    """
    utility function that returns a
    node class and it's weight 
    can be used for statistics
    to get some stats when NO Advanced Nodes are available
    """
    k = obj.__class__.__name__
    if k in ('Text',):
        return k, len(obj.caption) 
    elif k == 'ImageLink' and obj.isInline():
        return 'InlineImageLink', 1
    return k, 1

# -- extract text from pdf file. used for testing only.
def pdf2txt(path):
    """extract text from pdf file"""
    # based on http://code.activestate.com/recipes/511465/
    import pyPdf
    
    content = []
    pdf = pyPdf.PdfFileReader(file(path, "rb"))
    
    numpages = pdf.getNumPages()
    for i in range(0, numpages):
        # Extract text from page and add to content
        content.append(pdf.getPage(i).extractText())

    return "\n".join(content)



def garble_password(argv):
    argv = list(argv)
    idx = 0
    while True:
        try:
            idx = argv[idx:].index('--password') + 1
        except ValueError:
            break
        if idx >= len(argv):
            break
        argv[idx] = '{OMITTED}'
    return argv
