
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.txt for additional licensing information.

"""mz-zip - installed via setuptools' entry_points"""

import os
import tempfile
import shutil
import zipfile

def _walk(root):
    retval = []
    for dirpath, dirnames, files in os.walk(root):
        # retval.extend([os.path.normpath(os.path.join(dirpath, x))+"/" for x in dirnames])
        retval.extend([os.path.normpath(os.path.join(dirpath, x)) for x in files])
    retval = [x.replace("\\", "/") for x in retval]
    retval.sort()
    return retval

                     
def zipdir(dirname, output=None):
    """recursively zip directory and write output to zipfile.
    @param dirname: directory to zip
    @param output: name of zip file that get's written
    """
    if not output:
        output = dirname+".zip"

    output = os.path.abspath(output)
    cwd = os.getcwd()
    try:
        os.chdir(dirname)
        files = _walk(".")
        zf = zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED)
        for i in files:
            if i.endswith("/"):
                zf.writestr(zipfile.ZipInfo(i), "")
            else:
                zf.write(i)
        zf.close()
    finally:
        os.chdir(cwd)



        
def make_zip(output=None, options=None, metabook=None, podclient=None, status=None):
    if output:
        tmpdir = tempfile.mkdtemp(dir=os.path.dirname(output))
    else:
        tmpdir = tempfile.mkdtemp()
        
    try:
        fsdir = os.path.join(tmpdir, 'nuwiki')
        print 'creating nuwiki in %r' % fsdir
        from mwlib.apps.make_nuwiki import make_nuwiki
        make_nuwiki(fsdir, metabook=metabook, options=options, podclient=podclient, status=status)

        if output:
            fd, filename = tempfile.mkstemp(suffix='.zip', dir=os.path.dirname(output))
        else:
            fd, filename = tempfile.mkstemp(suffix='.zip')
        os.close(fd)
        zipdir(fsdir, filename)
        if output:
            os.rename(filename, output)
            filename = output

        if podclient:                
            status(status='uploading', progress=0)
            podclient.post_zipfile(filename)

        return filename

    finally:
        if not options.keep_tmpfiles:
            print 'removing tmpdir %r' % tmpdir
            shutil.rmtree(tmpdir, ignore_errors=True)
        else:
            print 'keeping tmpdir %r' % tmpdir

        
def main():    
    from mwlib.options import OptionParser

    parser = OptionParser()
    parser.add_option("-o", "--output", help="write output to OUTPUT")
    parser.add_option("-p", "--posturl", help="http post to POSTURL (directly)")
    parser.add_option("-g", "--getposturl",
        help='get POST URL from PediaPress.com, open upload page in webbrowser',
        action='store_true',
    )
    parser.add_option('--keep-tmpfiles',                  
        action='store_true',
        default=False,
        help="don't remove  temporary files like images",
    )
    
    parser.add_option("-s", "--status-file",
                      help='write status/progress info to this file')

    options, args = parser.parse_args()
    
    use_help = 'Use --help for usage information.'
        
                        
    if parser.metabook is None and options.collectionpage is None:
        parser.error('Neither --metabook nor, --collectionpage or arguments specified.\n' + use_help)
    if options.posturl and options.getposturl:
        parser.error('Specify either --posturl or --getposturl.\n' + use_help)
    if not options.posturl and not options.getposturl and not options.output:
        parser.error('Neither --output, nor --posturl or --getposturl specified.\n' + use_help)
    if options.posturl:
        from mwlib.podclient import PODClient
        podclient = PODClient(options.posturl)
    elif options.getposturl:
        import webbrowser
        from mwlib.podclient import podclient_from_serviceurl
        podclient = podclient_from_serviceurl('http://pediapress.com/api/collections/')
        pid = os.fork()
        if not pid:
            try:
                webbrowser.open(podclient.redirecturl)
            finally:
                os._exit(0)
        import time
        time.sleep(1)
        try:
            os.kill(pid, 9)
        except:
            pass
              
    else:
        podclient = None
    
    from mwlib import utils,  wiki
    
    if options.daemonize:
        utils.daemonize()
    if options.pid_file:
        open(options.pid_file, 'wb').write('%d\n' % os.getpid())

    filename = None
    status = None
    try:
        env = parser.makewiki()
        assert env.metabook, "no metabook"
            
        from mwlib.status import Status
        status = Status(options.status_file, podclient=podclient, progress_range=(1, 90))
        status(progress=0)
        output = options.output
            
        make_zip(output, options, env.metabook, podclient=podclient, status=status)
            
    except Exception, e:
        if status:
            status(status='error')
        raise
    finally:
        if options.output is None and filename is not None:
            print 'removing %r' % filename
            utils.safe_unlink(filename)
        if options.pid_file:
            utils.safe_unlink(options.pid_file)
