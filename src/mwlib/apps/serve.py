import argparse
import sys
import time

from mwlib.core.serve import purge_cache
from mwlib.networking.client import Client
from mwlib.utilities import utils
from mwlib.utilities.log import Log


def serve_ctl(args):
    if args.purge_cache:
        try:
            args.purge_cache = int(args.purge_cache)
        except ValueError:
            raise ValueError("--purge-cache value must be a positive number")

        purge_cache(args.purge_cache * 60 * 60, cache_dir=args.cache_dir)


def check_req(client, report, command, **kwargs):
    try:
        success = client.request(command, kwargs,
                                 is_json=(command != "download"))
    except Exception as exc:
        report("request failed: %s" % exc)
        sys.exit(1)
    if success:
        return client.response
    if client.error is not None:
        report("request failed: %s" % client.error)
        sys.exit(1)
    else:
        report("request failed: got response code %d" % client.response_code)
        sys.exit(1)


def get_report_func(args, log):
    def report_default(msg):
        log.ERROR(msg)

    if args.report_recipient and args.report_from_mail:
        def report_email(msg):
            utils.report(
                system="mw-check-service",
                subject="mw-check-service error",
                from_email=args.report_from_mail.encode("utf-8"),
                mail_recipients=[args.report_recipient.encode("utf-8")],
                msg=msg,
            )
        return report_email
    else:
        return report_default


def check_service(args):
    log = Log("mw-check-service")

    base_url = args.base_url
    with open(args.metabook, "rb") as metabook_file:
        metabook = metabook_file.read()

    max_render_time = int(args.max_render_time)
    writer = args.writer

    if args.logfile:
        utils.start_logging(args.logfile)

    client = Client(args.url)

    start_time = time.time()

    log.info("sending render command")
    response = check_req(
        "render",
        base_url=base_url,
        metabook=metabook,
        writer=writer,
        force_render=True,
    )
    collection_id = response["collection_id"]
    report = get_report_func(args, log)

    while True:
        time.sleep(1)

        if time.time() - start_time > max_render_time:
            report("rendering exceeded allowed time of %d s" % max_render_time)
            sys.exit(2)

        log.info("checking status")
        response = check_req(
            client, report,
            "render_status",
            collection_id=collection_id,
            writer=writer,
        )
        if response["state"] == "finished":
            break

    log.info("downloading")
    response = check_req(
        client, report,
        "download",
        collection_id=collection_id,
        writer=writer,
    )

    if len(response) < 100:
        report("got suspiciously small file from download: size is %d Bytes" % len(response))
        sys.exit(3)
    log.info("resulting file is %d Bytes" % len(response))

    if args.save_output:
        log.info("saving to %r" % args.save_output)
        with open(args.save_output, "wb") as out_file:
            out_file.write(response)

    render_time = time.time() - start_time
    log.info("rendering ok, took %fs" % render_time)


def parse_arguments():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    serve_ctl_parser = subparsers.add_parser("serve_ctl")
    serve_ctl_parser.add_argument(
        "--cache-dir",
        help="cache directory (default: /var/cache/mw-serve/)",
        default="/var/cache/mw-serve/",
    )
    serve_ctl_parser.add_argument(
        "--purge-cache",
        help="remove cache files that have not been touched for at least HOURS hours",
        metavar="HOURS",
    )
    serve_ctl_parser.set_defaults(func=serve_ctl)

    check_service_parser = subparsers.add_parser("check_service")
    default_url = "http://localhost:8899/"
    check_service_parser.add_argument(
        "-u",
        "--url",
        help="URL of HTTP interface to mw-serve (default: %r)" % default_url,
        default=default_url,
    )
    check_service_parser.add_argument(
        "-w",
        "--writer",
        help="writer to use for rendering (default: rl)",
        default="rl",
    )
    check_service_parser.add_argument(
        "--max-render-time",
        help="maximum number of seconds rendering may take (default: 120)",
        default="120",
        metavar="SECONDS",
    )
    check_service_parser.add_argument(
        "--save-output",
        help="if specified, save rendered file with given filename",
        metavar="FILENAME",
    )
    check_service_parser.add_argument(
        "-l",
        "--logfile",
        help="log output to LOGFILE",
    )
    check_service_parser.add_argument(
        "--report-from-mail",
        help="sender of error mails (--report-recipient also needed)",
        metavar="EMAIL",
    )
    check_service_parser.add_argument(
        "--report-recipient",
        help="recipient of error mails (--report-from-mail also needed)",
        metavar="EMAIL",
    )
    check_service_parser.add_argument(
        "base_url",
        help="Base URL of the MediaWiki instance",
    )
    check_service_parser.add_argument(
        "metabook",
        help="Path to the metabook file",
        type=argparse.FileType("rb"),
    )
    check_service_parser.set_defaults(func=check_service)

    return parser.parse_args()


def main():
    args = parse_arguments()
    args.func(args)


if __name__ == "__main__":
    main()
