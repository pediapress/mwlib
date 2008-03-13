import os
import sys
import errno

def daemonize(dev_null=True):
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
