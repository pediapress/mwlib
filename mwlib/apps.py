
# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.

"""main programs - installed via setuptools' entry_points"""

import optparse
import os

def buildcdb():
    parser = optparse.OptionParser(usage="%prog --input XMLDUMP --output OUTPUT")
    parser.add_option("-i", "--input", help="input file")
    parser.add_option("-o", "--output", help="write output to OUTPUT")
    options, args = parser.parse_args()
    
    if args:
        parser.error("too many arguments.")

    
    input = options.input
    output = options.output

    if not (input and output):
        parser.error("missing argument.")
        
    from mwlib import cdbwiki

    cdbwiki.BuildWiki(input, output)()
    open(os.path.join(output, "wikiconf.txt"), "w").write("""
[wiki]
type = cdb
path = %s

[images]
type = download
url = http://upload.wikimedia.org/wikipedia/commons/
localpath = ~/images
""" % (os.path.abspath(output),))

def show():
    parser = optparse.OptionParser()
    parser.add_option("-c", "--config", help="configuration file/URL/shortcut")
    parser.add_option("-e", "--expand", action="store_true", help="expand templates")
    parser.add_option("-t", "--template", action="store_true", help="show template")
    parser.add_option("-f", help='read input from file. implies -e')
    
    options, args = parser.parse_args()
    
    if not args and not options.f:
        parser.error("missing ARTICLE argument")
        
    articles = [unicode(x, 'utf-8') for x in args]

    conf = options.config
    if not conf:
        parser.error("missing --config argument")

    from mwlib import wiki, expander
    
    db = wiki.makewiki(conf)['wiki']
    
    for a in articles:
        if options.template:
            raw=db.getTemplate(a)
        else:
            raw=db.getRawArticle(a)

        if raw:
            if options.expand:
                te = expander.Expander(raw, pagename=a, wikidb=db)
                raw = te.expandTemplates()

            print raw.encode("utf-8")
    if options.f:
        raw = unicode(open(options.f).read(), 'utf-8')
        te = expander.Expander(raw, pagename='test', wikidb=db)
        raw = te.expandTemplates()
        print raw.encode("utf-8")

def buildzip():
    from mwlib.options import OptionParser

    parser = OptionParser()
    parser.add_option("-o", "--output", help="write output to OUTPUT")
    parser.add_option("-p", "--posturl", help="http post to POSTURL (directly)")
    parser.add_option("-g", "--getposturl",
        help='get POST URL from PediaPress.com, open upload page in webbrowser',
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
        webbrowser.open(podclient.redirecturl)
    else:
        podclient = None
    
    from mwlib import utils
    
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
            from mwlib import zipcreator
        
            status = Status(podclient=podclient, progress_range=(1, 90))
            status(status='parsing', progress=0)
            
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

def post():
    parser = optparse.OptionParser(usage="%prog OPTIONS")
    parser.add_option("-i", "--input", help="ZIP file to POST")
    parser.add_option('-l', '--logfile',
        help='log output to LOGFILE',
    )
    parser.add_option("-p", "--posturl", help="HTTP POST ZIP file to POSTURL")
    parser.add_option("-g", "--getposturl",
        help='get POST URL from PediaPress.com, open upload page in webbrowser',
        action='store_true',
    )
    parser.add_option("-d", "--daemonize", action="store_true",
        help='become a daemon process as soon as possible')
    parser.add_option('--pid-file',
        help='write PID of daemonized process to this file',
    )
    options, args = parser.parse_args()
    
    use_help = 'Use --help for usage information.'
    if not options.input:
        parser.error('Specify --input.\n' + use_help)
    if (options.posturl and options.getposturl)\
        or (not options.posturl and not options.getposturl):
        parser.error('Specify either --posturl or --getposturl.\n' + use_help)
    if options.posturl:
        from mwlib.podclient import PODClient
        podclient = PODClient(options.posturl)
    elif options.getposturl:
        import webbrowser
        from mwlib.podclient import podclient_from_serviceurl
        podclient = podclient_from_serviceurl('http://pediapress.com/api/collections/')
        webbrowser.open(podclient.redirecturl)
    
    from mwlib import utils
    from mwlib.status import Status
    
    if options.logfile:
        utils.start_logging(options.logfile)
    
    if options.daemonize:
        utils.daemonize()
    if options.pid_file:
        open(options.pid_file, 'wb').write('%d\n' % os.getpid())
    
    
    status = Status(podclient=podclient)
    
    try:
        try:
            status(status='uploading', progress=0)
            podclient.post_zipfile(options.input)
            status(status='finished', progress=100)
        except Exception, e:
            status(status='error')
            raise
    finally:
        if options.pid_file:
            utils.safe_unlink(options.pid_file)

def render():
    from mwlib.options import OptionParser
    
    parser = OptionParser(config_optional=True)
    parser.add_option("-o", "--output", help="write output to OUTPUT")
    parser.add_option("-w", "--writer", help='use writer backend WRITER')
    parser.add_option("-W", "--writer-options",
        help='";"-separated list of additional writer-specific options',
    )
    parser.add_option("-e", "--error-file", help='write errors to this file')
    parser.add_option("-s", "--status-file",
        help='write status/progress info to this file',
    )
    parser.add_option("--list-writers",
        action='store_true',
        help='list available writers and exit',
    )
    parser.add_option("--writer-info",
        help='list information about given WRITER and exit',
        metavar='WRITER',
    )
    parser.add_option('--keep-zip',
        help='write ZIP file to FILENAME',
        metavar='FILENAME',
    )
    parser.add_option('--keep-tmpfiles',                  
                      action='store_true',
                      default=False,
                      help="don't remove  temporary files like images",
                      )
    
    options, args = parser.parse_args()
    
    import sys
    import tempfile
    import traceback
    import pkg_resources
    from mwlib.mwapidb import MWAPIError
    from mwlib.writerbase import WriterError
    from mwlib import utils, zipwiki, zipcreator
    from mwlib.status import Status
    
    use_help = 'Use --help for usage information.'
    
    def load_writer(name):
        try:
            entry_point = pkg_resources.iter_entry_points('mwlib.writers', name).next()
        except StopIteration:
            sys.exit('No such writer: %r (use --list-writers to list available writers)' % name)
        try:
            return entry_point.load()
        except Exception, e:
            sys.exit('Could not load writer %r: %s' % (name, e))
    
    if options.list_writers:
        for entry_point in pkg_resources.iter_entry_points('mwlib.writers'):
            try:
                writer = entry_point.load()
                if hasattr(writer, 'description'):
                    description = writer.description
                else:
                    description = '<no description>'
            except Exception, e:
                description = '<NOT LOADABLE: %s>' % e
            print '%s\t%s' % (entry_point.name, description)
        return
    
    if options.writer_info:
        writer = load_writer(options.writer_info)
        if hasattr(writer, 'description'):
            print 'Description:\t%s' % writer.description
        if hasattr(writer, 'content_type'):
            print 'Content-Type:\t%s' % writer.content_type
        if hasattr(writer, 'file_extension'):
            print 'File extension:\t%s' % writer.file_extension
        if hasattr(writer, 'options') and writer.options:
            print 'Options (usable in a ";"-separated list for --writer-options):'
            for name, info in writer.options.items():
                param = info.get('param')
                if param:
                    print ' %s=%s:\t%s' % (name, param, info['help'])
                else:
                    print ' %s:\t%s' % (name, info['help'])
        return
    
    if options.config is None:
        parser.error('Please specify --config.\n' + use_help)
    
    if options.output is None:
        parser.error('Please specify an output file with --output.\n' + use_help)
    else:
        options.output = os.path.abspath(options.output)
        
    if options.writer is None:
        parser.error('Please specify a writer with --writer.\n' + use_help)    
    
    writer = load_writer(options.writer)
    writer_options = {}
    if options.writer_options:
        for wopt in options.writer_options.split(';'):
            if '=' in wopt:
                key, value = wopt.split('=', 1)
                writer_options[key] = value
            else:
                writer_options[wopt] = True
    
    if options.daemonize:
        utils.daemonize()
    if options.pid_file:
        open(options.pid_file, 'wb').write('%d\n' % os.getpid())
    
    status = Status(options.status_file, progress_range=(1, 70))
    status(status='parsing', progress=0)
    
    env = None
    try:
        try:
            env = parser.makewiki()
        
            if not isinstance(env.wiki, zipwiki.Wiki)\
                or not isinstance(env.images, zipwiki.ImageDB):
                zip_filename = zipcreator.make_zip_file(options.keep_zip, env,
                    status=status,
                    num_threads=options.num_threads,
                    imagesize=options.imagesize,
                )
                if env.images:
                    env.images.clear()
                env.wiki = zipwiki.Wiki(zip_filename)
                env.images = zipwiki.ImageDB(zip_filename)
            else:
                zip_filename = None
            
            print 'START WITH PROGRESS'
            status = Status(options.status_file, progress_range=(71, 100))
            status(status='rendering', progress=0)
            
            fd, tmpout = tempfile.mkstemp(dir=os.path.dirname(options.output))
            os.close(fd)
            writer(env, output=tmpout, status_callback=status, **writer_options)
            os.rename(tmpout, options.output)
            kwargs = {}
            if hasattr(writer, 'content_type'):
                kwargs['content_type'] = writer.content_type
            if hasattr(writer, 'file_extension'):
                kwargs['file_extension'] = writer.file_extension
            status(status='finished', progress=100, **kwargs)
            if options.keep_zip is None and zip_filename is not None:
                utils.safe_unlink(zip_filename)
        except Exception, e:
            status(status='error')
            if options.error_file:
                fd, tmpfile = tempfile.mkstemp(dir=os.path.dirname(options.error_file))
                f = os.fdopen(fd, 'wb')
                if isinstance(e, WriterError) or isinstance(e, MWAPIError):
                    f.write(str(e))
                else:
                    traceback.print_exc(file=f) 
                f.close()
                os.rename(tmpfile, options.error_file)
            raise
    finally:
        if env is not None and env.images is not None:
            try:
                if not options.keep_tmpfiles:
                    env.images.clear()
                else:
                    pass
            except Exception, e:
                print 'ERROR: Could not remove temporary images: %s' % e
        if options.pid_file:
            utils.safe_unlink(options.pid_file)

def parse():
    parser = optparse.OptionParser(usage="%prog [-a|--all] --config CONFIG [ARTICLE1 ...]")
    parser.add_option("-a", "--all", action="store_true", help="parse all articles")
    parser.add_option("--tb", action="store_true", help="show traceback on error")

    parser.add_option("-c", "--config", help="configuration file/URL/shortcut")

    options, args = parser.parse_args()
                                   
    if not args and not options.all:
        parser.error("missing option.")
        
    if not options.config:
        parser.error("missing --config argument")

    articles = [unicode(x, 'utf-8') for x in args]

    conf = options.config
    
    import traceback
    from mwlib import wiki, uparser
    
    w = wiki.makewiki(conf)
    
    db = w['wiki']

    if options.all:
        if not hasattr(db, "articles"):
            raise RuntimeError("%s does not support iterating over all articles" % (db, ))
        articles = db.articles()


    import time
    for x in articles:
        try:
            raw = db.getRawArticle(x)
            # yes, raw can be None, when we have a redirect to a non-existing article.
            if raw is None: 
                continue
            stime=time.time()
            a=uparser.parseString(x, raw=raw, wikidb=db)
        except Exception, err:
            print "F", repr(x), err
            if options.tb:
                traceback.print_exc()
        else:
            print "G", time.time()-stime, repr(x)



def serve():
    from SocketServer import ForkingMixIn, ThreadingMixIn
    from wsgiref.simple_server import make_server, WSGIServer
    from flup.server import fcgi, fcgi_fork, scgi, scgi_fork
    
    class ForkingWSGIServer(ForkingMixIn, WSGIServer):
        pass
    
    class ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
        pass
    
    proto2server = {
        'http': ForkingWSGIServer,
        'http_threaded': ThreadingWSGIServer,
        'fcgi': fcgi_fork.WSGIServer,
        'fcgi_threaded': fcgi.WSGIServer,
        'scgi': scgi_fork.WSGIServer,
        'scgi_threaded': scgi.WSGIServer,
    }
    
    parser = optparse.OptionParser(usage="%prog [OPTIONS]")
    parser.add_option('-l', '--logfile',
        help='log output to LOGFILE',
    )
    parser.add_option('-d', '--daemonize',
        action='store_true',
        help='become daemon as soon as possible',
    )
    parser.add_option('--pid-file',
        help='write PID of daemonized process to this file',
    )
    parser.add_option('-P', '--protocol',
        help='one of %s (default: http)' % ', '.join(proto2server.keys()),
        default='http',
    )
    parser.add_option('-p', '--port',
        help='port to listen on (default: 8899)',
        default='8899',
    )
    parser.add_option('-i', '--interface',
        help='interface to listen on (default: 0.0.0.0)',
        default='0.0.0.0',
    )
    parser.add_option('--cache-dir',
        help='cache directory (default: /var/cache/mw-serve/)',
        default='/var/cache/mw-serve/',
    )
    parser.add_option('--mwrender',
        help='(path to) mw-render executable',
        default='mw-render',
    )
    parser.add_option('--mwrender-logfile',
        help='global logfile for mw-render',
        metavar='LOGFILE',
    )
    parser.add_option('--mwzip',
        help='(path to) mw-zip executable',
        default='mw-zip',
    )
    parser.add_option('--mwzip-logfile',
        help='global logfile for mw-zip',
        metavar='LOGFILE',
    )
    parser.add_option('--mwpost',
        help='(path to) mw-post executable',
        default='mw-post',
    )
    parser.add_option('--mwpost-logfile',
        help='global logfile for mw-post',
        metavar='LOGFILE',
    )
    parser.add_option('-q', '--queue-dir',
        help='queue dir of mw-watch (if not specified, no queue is used)',
    )
    parser.add_option('-m', '--method',
        help='prefork or threaded (default: prefork)',
        default='prefork',
    )
    parser.add_option('--max-requests',
        help='maximum number of requests a child process can handle before it is killed, irrelevant for --method=threaded (default: 0 = no limit)',
        default='0',
        metavar='NUM',
    )
    parser.add_option('--min-spare',
        help='minimum number of spare processes/threads (default: 2)',
        default='2',
        metavar='NUM',
    )
    parser.add_option('--max-spare',
        help='maximum number of spare processes/threads (default: 5)',
        default='5',
        metavar='NUM',
    )
    parser.add_option('--max-children',
        help='maximum number of processes/threads (default: 50)',
        default='50',
        metavar='NUM',
    )
    parser.add_option('--report-from-mail',
        help='sender of error mails (--report-recipient also needed)',
        metavar='EMAIL',
    )
    parser.add_option('--report-recipient',
        help='recipient of error mails (--report-from-mail also needed)',
        metavar='EMAIL',
    )
    parser.add_option('--clean-cache',
        help='clean cache files that have not been touched for at least HOURS hours and exit',
        metavar='HOURS',
    )
    options, args = parser.parse_args()
    
    if options.clean_cache:
        try:
            options.clean_cache = int(options.clean_cache)
        except ValueError:
            parser.error('--clean-cache value must be an integer')
        from mwlib.serve import clean_cache
        clean_cache(options.clean_cache*60*60, cache_dir=options.cache_dir)
        return
    
    if options.protocol not in proto2server:
        parser.error('unsupported protocol (must be one of %s)' % (
            ', '.join(proto2server.keys()),
        ))

    def to_int(opt_name):
        try:
            setattr(options, opt_name, int(getattr(options, opt_name)))
        except ValueError:
            parser.error('--%s value must be an integer' % opt_name.replace('_', '-'))
    
    to_int('port')
    to_int('max_requests')
    to_int('min_spare')
    to_int('max_spare')
    to_int('max_children')
    
    if options.method not in ('prefork', 'threaded'):
        parser.error('the only supported values for --method are "prefork" and "threaded"')
    
    from mwlib import serve, log, utils
    
    log = log.Log('mw-serve')
    
    if options.logfile:
        utils.start_logging(options.logfile)
    
    if options.daemonize:
        utils.daemonize()
    if options.pid_file:
        open(options.pid_file, 'wb').write('%d\n' % os.getpid())
    
    if options.method == 'threaded':
        options.protocol += '_threaded'
        flup_kwargs = {
            'maxThreads': options.max_children,
        }
    else:
        flup_kwargs = {
            'maxChildren': options.max_children,
            'maxRequests':  options.max_requests,
        }
    
    log.info("serving %s on %s:%s" % (options.protocol, options.interface, options.port))
    
    if options.report_recipient and options.report_from_mail:
        report_from_mail = options.report_from_mail.encode('utf-8')
        report_recipients = [options.report_recipient.encode('utf-8')]
    else:
        report_from_mail = None
        report_recipients = None
    
    app = serve.Application(
        cache_dir=options.cache_dir,
        mwrender_cmd=options.mwrender,
        mwrender_logfile=options.mwrender_logfile,
        mwzip_cmd=options.mwzip,
        mwzip_logfile=options.mwzip_logfile,
        mwpost_cmd=options.mwpost,
        mwpost_logfile=options.mwpost_logfile,
        queue_dir=options.queue_dir,
        report_from_mail=report_from_mail,
        report_recipients=report_recipients,
    )
    if options.protocol.startswith('http'):
        server = make_server(options.interface, options.port, app,
            server_class=proto2server[options.protocol],
        )
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    else:
        serverclass = proto2server[options.protocol]
        serverclass(app,
            bindAddress=(options.interface, options.port),
            minSpare=options.min_spare,
            maxSpare=options.max_spare,
            **flup_kwargs
        ).run()
    
    if options.pid_file:
        utils.safe_unlink(options.pid_file)
    
    log.info('exit.')

def watch():
    parser = optparse.OptionParser(usage="%prog [OPTIONS]")
    parser.add_option('-l', '--logfile',
        help='log output to LOGFILE',
    )
    parser.add_option('-d', '--daemonize',
        action='store_true',
        help='become daemon as soon as possible',
    )
    parser.add_option('--pid-file',
        help='write PID of daemonized process to this file',
    )
    parser.add_option('-q', '--queue-dir',
        help='queue directory, where new job files are written to (default: /var/cache/mw-watch/q/)',
        default='/var/cache/mw-watch/q/',
    )
    parser.add_option('-p', '--processing-dir',
        help='processing directory, where active job files are moved to (must be on same filesystem as --queue-dir, default: /var/cache/mw-watch/p/)',
        default='/var/cache/mw-watch/p/',
    )
    parser.add_option('-n', '--num-jobs',
        help='maximum number of simulataneous jobs (default: 5)',
        default='5',
    )
    options, args = parser.parse_args()
    
    try:
        options.num_jobs = int(options.num_jobs)
    except ValueError:
        parser.error('--num-jobs value must be an integer')
    
    from mwlib import filequeue, utils
    
    if options.logfile:
        utils.start_logging(options.logfile)
    
    if options.daemonize:
        utils.daemonize()
    if options.pid_file:
        open(options.pid_file, 'wb').write('%d\n' % os.getpid())
    
    poller = filequeue.FileJobPoller(
        queue_dir=options.queue_dir,
        processing_dir=options.processing_dir,
        max_num_jobs=options.num_jobs,
    ).run_forever()
    
    if options.pid_file:
        utils.safe_unlink(options.pid_file)

def testserve():
    parser = optparse.OptionParser(usage="%prog --config CONFIG ARTICLE [...]")
    parser.add_option("-c", "--config", help="configuration file/URL/shortcut")

    options, args = parser.parse_args()
    

    conf = options.config
    if not conf:
        parser.error("missing --config argument")
    
    from mwlib import wiki, web
    
    res = wiki.makewiki(conf)
    db = res['wiki']
    images = res['images']
    from wsgiref.simple_server import make_server, WSGIServer

    from SocketServer import  ForkingMixIn
    class MyServer(ForkingMixIn, WSGIServer):
        pass

    iface, port = '0.0.0.0', 8080
    print "serving on %s:%s" % (iface, port)
    http = make_server(iface, port, web.Serve(db, res['images']), server_class=MyServer)
    http.serve_forever()
    

    
def html():
    parser = optparse.OptionParser(usage="%prog --config CONFIG ARTICLE [...]")
    parser.add_option("-c", "--config", help="configuration file/URL/shortcut")

    options, args = parser.parse_args()
    
    if not args:
        parser.error("missing ARTICLE argument")
        
    articles = [unicode(x, 'utf-8') for x in args]

    conf = options.config
    if not conf:
        parser.error("missing --config argument")
    
    import StringIO
    import tempfile
    import webbrowser
    from mwlib import wiki, uparser, htmlwriter
    
    res = wiki.makewiki(conf)
    db = res['wiki']
    images = res['images']

    for a in articles:
        raw=db.getRawArticle(a)
        if not raw:
            continue

        out=StringIO.StringIO()
        out.write("""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
<head>
<meta http-equiv="content-type" content="text/html; charset="utf-8"></meta>
<link rel="stylesheet" href="pedia.css" />
</head>
<body>

""")

        a=uparser.parseString(x, raw=raw, wikidb=db)
        w=htmlwriter.HTMLWriter(out, images)
        w.write(a)

        fd, htmlfile = tempfile.mkstemp(".html")
        os.close(fd)
        open(htmlfile, "wb").write(out.getvalue().encode('utf-8'))
        webbrowser.open("file://"+htmlfile)
