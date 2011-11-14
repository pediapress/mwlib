import optparse


def serve_ctl():
    parser = optparse.OptionParser(usage="%prog [OPTIONS]")
    parser.add_option('--cache-dir',
        help='cache directory (default: /var/cache/mw-serve/)',
        default='/var/cache/mw-serve/',
    )
    parser.add_option('--purge-cache',
        help='remove cache files that have not been touched for at least HOURS hours',
        metavar='HOURS',
    )

    options, args = parser.parse_args()

    if args:
        parser.error('no arguments supported')

    if options.purge_cache:
        try:
            options.purge_cache = float(options.purge_cache)
        except ValueError:
            parser.error('--purge-cache value must be a positive number')

        from mwlib.serve import purge_cache
        purge_cache(options.purge_cache*60*60, cache_dir=options.cache_dir)


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
