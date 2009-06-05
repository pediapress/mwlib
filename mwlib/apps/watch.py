import optparse
import os

def main():
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

