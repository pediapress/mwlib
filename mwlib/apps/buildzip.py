
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
        
def hack(options=None, env=None, podclient=None, status=None, **kwargs):
    imagesize = options.imagesize
    metabook = env.metabook
    base_url = env.wiki.api_helper.base_url
    script_extension = env.wiki.api_helper.script_extension
    api_url = "".join([base_url, "api", script_extension])
    output = options.output

    
    if output:
        fsdir = output+".nuwiki"
    else:
        fsdir = tempfile.mkdtemp(prefix="nuwiki-")

    if os.path.exists(fsdir):
        shutil.rmtree(fsdir)
        

    
    from mwlib import twisted_api
    from twisted.internet import reactor
    

    fsout = twisted_api.fsoutput(fsdir)

    def doit():
        api = twisted_api.mwapi(api_url)
        fsout.dump_json(metabook=metabook)
        fsout.dump_json(nfo=dict(format="nuwiki"))
        
        pages = twisted_api.pages_from_metabook(metabook)
        
        twisted_api.fetcher(api, fsout, pages, podclient=podclient)

    try:
        if podclient is not None:
            old_class = podclient.__class__
            podclient.__class__ = twisted_api.PODClient

        reactor.callLater(0.0, doit)
        reactor.run()
    finally:        
        print "done"
        if podclient is not None:
            podclient.__class__ = old_class
    
    if output:
        filename = output
    else:
        filename = tempfile.mktemp()
        
    zipdir(fsdir, filename)
    
    if podclient:                
        status(status='uploading', progress=0)
        podclient.post_zipfile(filename)

def main():    
    from mwlib.options import OptionParser

    parser = OptionParser()
    parser.add_option("-o", "--output", help="write output to OUTPUT")
    parser.add_option("-p", "--posturl", help="http post to POSTURL (directly)")
    parser.add_option("-g", "--getposturl",
        help='get POST URL from PediaPress.com, open upload page in webbrowser',
        action='store_true',
    )
    parser.add_option('-f', '--fastzipcreator',
        help='Use experimental new fzipcreator code',
        action='store_true',
    )
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
    
    from mwlib import utils, mwapidb
    
    if options.daemonize:
        utils.daemonize()
    if options.pid_file:
        open(options.pid_file, 'wb').write('%d\n' % os.getpid())

    filename = None
    status = None
    try:
        try:
            env = parser.makewiki()
            from mwlib.status import Status
            status = Status(podclient=podclient, progress_range=(1, 90))
            status(progress=0)
            
            if isinstance(env.wiki, mwapidb.WikiDB):
                hack(**locals())
            else:    
                if options.fastzipcreator:
                    import mwlib.fzipcreator as zipcreator
                else:
                    from mwlib import zipcreator


                filename = zipcreator.make_zip_file(options.output, env,
                    status=status,
                    num_threads=options.num_threads,
                    imagesize=options.imagesize,
                )

                status = Status(podclient=podclient, progress_range=(91, 100))
                if podclient:
                    status(status='uploading', progress=0)
                    podclient.post_zipfile(filename)

                status(status='finished', progress=100)
        except Exception, e:
            import traceback
            traceback.print_exc()
            print "ERROR:", e
            if status:
                status(status='error')
            raise
    finally:
        if options.output is None and filename is not None:
            print 'removing %r' % filename
            utils.safe_unlink(filename)
        if options.pid_file:
            utils.safe_unlink(options.pid_file)
