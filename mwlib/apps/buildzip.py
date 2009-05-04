
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.txt for additional licensing information.

"""mz-zip - installed via setuptools' entry_points"""

import sys
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
        
def hack(output=None, options=None, env=None, podclient=None, status=None, keep_tmpfiles=False, **kwargs):
    imagesize = options.imagesize
    metabook = env.metabook
    base_url = env.wiki.api_helper.base_url
    script_extension = env.wiki.api_helper.script_extension
    api_url = "".join([base_url, "api", script_extension])

    template_exclusion_category = options.template_exclusion_category
    print_template_pattern = options.print_template_pattern
    
    
    if output:
        fsdir = output+".nuwiki"
    else:
        fsdir = tempfile.mkdtemp(prefix="nuwiki-")

    if os.path.exists(fsdir):
        shutil.rmtree(fsdir)
        

    
    from mwlib import twisted_api
    from mwlib.metabook import get_licenses
    from twisted.internet import reactor
    
    


    
    options.fetcher = None # stupid python
    fsout = twisted_api.FSOutput(fsdir)
    
    def doit():
        api = twisted_api.mwapi(api_url)
        fsout.dump_json(metabook=metabook)
        nfo = {
            'format': 'nuwiki',
            'base_url': base_url,
            'script_extension': script_extension,
        }
        if print_template_pattern:
            nfo["print_template_pattern"] = print_template_pattern
         
        fsout.dump_json(nfo=nfo)
        
        pages = twisted_api.pages_from_metabook(metabook)
        
        options.fetcher = twisted_api.Fetcher(api, fsout, pages,
                                              licenses=get_licenses(metabook),
                                              podclient=podclient,
                                              print_template_pattern=print_template_pattern,
                                              template_exclusion_category=template_exclusion_category)

    try:
        if podclient is not None:
            old_class = podclient.__class__
            podclient.__class__ = twisted_api.PODClient

        reactor.callLater(0.0, doit)
        reactor.run()
    finally:
        if podclient is not None:
            podclient.__class__ = old_class

    
    fetcher = options.fetcher
    if fetcher.fatal_error:
        print "error:", fetcher.fatal_error
        sys.exit(10)
    print "done"
    

    if output:
        filename = output
    else:
        filename = tempfile.mktemp(suffix=".zip")
        
    zipdir(fsdir, filename)

    if not keep_tmpfiles:
        print 'removing %r' % fsdir
        shutil.rmtree(fsdir, ignore_errors=True)
    
    if podclient:                
        status(status='uploading', progress=0)
        podclient.post_zipfile(filename)

    return filename

        
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
            output = options.output
            keep_tmpfiles = options.keep_tmpfiles
            
            if not options.oldzipcreator and isinstance(env.wiki, mwapidb.WikiDB):
                hack(**locals())
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
            if status:
                status(status='error')
            raise
    finally:
        if options.output is None and filename is not None:
            print 'removing %r' % filename
            utils.safe_unlink(filename)
        if options.pid_file:
            utils.safe_unlink(options.pid_file)
