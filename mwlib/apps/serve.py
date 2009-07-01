import optparse
import os

def main():
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

    if args:
        parser.error('no arguments supported')
    
    if options.clean_cache:
        print '''WARNING: This option of mw-serve is deprecated and will be removed:
Please use mw-serve-ctl --purge-cache instead!'''
        try:
            options.clean_cache = int(options.clean_cache)
        except ValueError:
            parser.error('--clean-cache value must be an integer')
        from mwlib.serve import purge_cache
        purge_cache(options.clean_cache*60*60, cache_dir=options.cache_dir)
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


def serve_ctl():
    from mwlib import utils

    parser = optparse.OptionParser(usage="%prog [OPTIONS]")
    parser.add_option('--cache-dir',
        help='cache directory (default: /var/cache/mw-serve/)',
        default='/var/cache/mw-serve/',
    )
    parser.add_option('--clean-up',
        help='report errors for died processes, kill long-running processes',
        action='store_true',
    )
    parser.add_option('--purge-cache',
        help='remove cache files that have not been touched for at least HOURS hours',
        metavar='HOURS',
    )
    parser.add_option('--max-running-time',
        help='number of seconds a process is allowed to run before it gets killed on --clean-up (default: 3600)',
        metavar='SECONDS',
        default='3600',
    )
    parser.add_option('--report-from-mail',
        help='sender of error mails (--report-recipient also needed)',
        metavar='EMAIL',
    )
    parser.add_option('--report-recipient',
        help='recipient of error mails (--report-from-mail also needed)',
        metavar='EMAIL',
    )
    options, args = parser.parse_args()

    if args:
        parser.error('no arguments supported')

    if options.report_recipient and options.report_from_mail:
        def report(msg):
            utils.report(
                system='mw-serve-ctl',
                subject='mw-serve-ctl error',
                from_email=options.report_from_mail.encode('utf-8'),
                mail_recipients=[options.report_recipient.encode('utf-8')],
                msg=msg,
            )
    else:
        report = None
    
    if options.purge_cache:
        try:
            options.purge_cache = int(options.purge_cache)
        except ValueError:
            parser.error('--purge-cache value must be an integer')

        from mwlib.serve import purge_cache

        purge_cache(options.purge_cache*60*60, cache_dir=options.cache_dir)

    if options.clean_up:
        from mwlib.serve import clean_up

        try:
            max_running_time = int(options.max_running_time)
        except ValueError:
            parser.error('--max-running-time value must be an integer')

        clean_up(cache_dir=options.cache_dir, max_running_time=max_running_time, report=report)


