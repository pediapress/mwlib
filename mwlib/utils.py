import os
import sys
import errno
import time

# provide all for python 2.4
try:
    from __builtin__ import all
except ImportError:
    def all(items):
        for x in items:
            if not x:
                return False
        return True

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

def shell_exec(cmd, maxmem=1024*1024, maxtime=60, maxfile=32*1024):
    """Execute cmd in a subshell. On Linux and Mac OS X the time and memory
    consumption is limited with ulimit.
    
    @param cmd: command to execute with os.system(), if given as unicode its
        converted to str using sys.getfilesystemencoding()
    @type cmd: basestring
    
    @param maxmem: max. KBytes of virtual memory
    @type maxmem: int
    
    @param maxtime: max. CPU time in seconds
    @type maxtime: int
    
    @param maxfile: max. KBytes of files written to disk
    @type maxfile: int
    
    @returns: exit code of command
    @rtype: int
    """
    if isinstance(cmd, unicode):
        enc = sys.getfilesystemencoding()
        assert enc is not None, 'no filesystem encoding (set LANG)'
        cmd = cmd.encode(enc)
    if sys.platform in ('darwin', 'linux2'):
        cmd = 'ulimit -v %d -t %d -f %d && %s' % (maxmem, maxtime, maxfile, cmd)
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
