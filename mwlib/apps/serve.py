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
    options, args = parser.parse_args()

    if args:
        parser.error('no arguments supported')
    
    
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
            options.purge_cache = float(options.purge_cache)
        except ValueError:
            parser.error('--purge-cache value must be a positive number')

        from mwlib.serve import purge_cache

        purge_cache(options.purge_cache*60*60, cache_dir=options.cache_dir)

    if options.clean_up:
        from mwlib.serve import clean_up

        try:
            max_running_time = int(options.max_running_time)
        except ValueError:
            parser.error('--max-running-time value must be an integer')

        clean_up(cache_dir=options.cache_dir, max_running_time=max_running_time, report=report)


def check_service():
    import sys
    import time

    from mwlib.client import Client
    from mwlib.log import Log
    from mwlib import utils

    log = Log('mw-check-service')

    parser = optparse.OptionParser(usage="%prog [OPTIONS] BASEURL METABOOK")
    default_url = 'http://localhost:8899/'
    parser.add_option('-u', '--url',
        help='URL of HTTP interface to mw-serve (default: %r)' % default_url,
        default=default_url,
    )
    parser.add_option('-w', '--writer',
        help='writer to use for rendering (default: rl)',
        default='rl',
    )
    parser.add_option('--max-render-time',
        help='maximum number of seconds rendering may take (default: 120)',
        default='120',
        metavar='SECONDS',
    )
    parser.add_option('--save-output',
        help='if specified, save rendered file with given filename',
        metavar='FILENAME',
    )
    parser.add_option('-l', '--logfile',
        help='log output to LOGFILE',
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

    if len(args) != 2:
        parser.error('exactly 2 arguments required')

    base_url = args[0]
    metabook = open(args[1], 'rb').read()

    max_render_time = int(options.max_render_time)

    if options.report_recipient and options.report_from_mail:
        def report(msg):
            utils.report(
                system='mw-check-service',
                subject='mw-check-service error',
                from_email=options.report_from_mail.encode('utf-8'),
                mail_recipients=[options.report_recipient.encode('utf-8')],
                msg=msg,
            )
    else:
        report = log.ERROR

    writer = options.writer

    if options.logfile:
        utils.start_logging(options.logfile)

    client = Client(options.url)

    def check_req(command, **kwargs):
        try:
            success = client.request(command, kwargs, is_json=(command != 'download'))
        except Exception, exc:
            report('request failed: %s' % exc)
            sys.exit(1)
        
        if success:
            return client.response
        if client.error is not None:
            report('request failed: %s' % client.error)
            sys.exit(1)
        else:
            report('request failed: got response code %d' % client.response_code)
            sys.exit(1)

    start_time = time.time()

    log.info('sending render command')
    response = check_req('render',
        base_url=base_url,
        metabook=metabook,
        writer=writer,
        force_render=True,
    )
    collection_id = response['collection_id']

    while True:
        time.sleep(1)

        if time.time() - start_time > max_render_time:
            report('rendering exceeded allowed time of %d s' % max_render_time)
            sys.exit(2)

        log.info('checking status')
        response = check_req('render_status',
            collection_id=collection_id,
            writer=writer,
        )
        if response['state'] == 'finished':
            break

    log.info('downloading')
    response = check_req('download',
        collection_id=collection_id,
        writer=writer,
    )

    if len(response) < 100:
        report('got suspiciously small file from download: size is %d Bytes' % len(response))
        sys.exit(3)
    log.info('resulting file is %d Bytes' % len(response))

    if options.save_output:
        log.info('saving to %r' % options.save_output)
        open(options.save_output, 'wb').write(response)

    render_time = time.time() - start_time
    log.info('rendering ok, took %fs' % render_time)

