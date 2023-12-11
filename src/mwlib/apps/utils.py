from gevent import monkey

from mwlib.apps.make_nuwiki import make_nuwiki
from mwlib.configuration import conf
from mwlib.miscellaneous.status import Status
from mwlib.utilities.options import OptionParser


def create_nuwiki(fsdir, options=None, metabook=None, podclient=None, status=None):
    print("creating nuwiki in %r" % fsdir)

    make_nuwiki(
        fsdir,
        metabook=metabook,
        options=options,
        podclient=podclient,
        status=status,
    )


def create_zip_from_wiki_env(parser, pod_client, options, make_zip):
    env = parser.make_wiki()
    if not env.metabook:
        raise ValueError("no metabook")
    status = Status(
        options.status_file, podclient=pod_client, progress_range=(1, 90)
    )
    status(progress=0)
    output = options.output
    make_zip(output, options, env.metabook, podclient=pod_client, status=status)
    return status


def build_parser():
    monkey.patch_all(thread=False)

    parser = OptionParser()
    parser.add_option("-o", "--output", help="write output to OUTPUT")
    parser.add_option("-p", "--posturl", help="http post to POSTURL (directly)")
    parser.add_option(
        "-g",
        "--getposturl",
        help="get POST URL from PediaPress.com, open upload page in webbrowser",
        action="count",
    )
    parser.add_option(
        "--keep-tmpfiles",
        action="store_true",
        default=False,
        help="don't remove  temporary files like images",
    )

    parser.add_option(
        "-s", "--status-file", help="write status/progress info to this file"
    )

    options, _ = parser.parse_args()
    conf.readrc()
    use_help = "Use --help for usage information."

    if parser.metabook is None and options.collectionpage is None:
        parser.error(
            "Neither --metabook nor, --collectionpage or arguments specified.\n"
            + use_help
        )
    return parser, options, use_help
