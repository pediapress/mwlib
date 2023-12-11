#! /usr/bin/env python


if __name__ == "__main__":
    from gevent import monkey

    monkey.patch_all()

import os
import socket
import sys
import time

from bottle import default_app, route, static_file
from qs import slave

from mwlib.asynchronous import proc
from mwlib.utilities import myjson
from mwlib.utilities.log import root_logger
from mwlib.utilities.utils import garble_password

logger = root_logger.getChild(__name__)

CACHE_DIR = None
CACHE_URL = None


# -- find_ip is copied from woof sources
# Utility function to guess the IP (as a string) where the server can
# be reached from the outside. Quite nasty problem actually.


def find_ip():
    # we get a UDP-socket for the TEST-networks reserved by IANA.  It
    # is highly unlikely, that there is special routing used for these
    # networks, hence the socket later should give us the ip address of
    # the default route.  We're doing multiple tests, to guard against
    # the computer being part of a test installation.

    candidates = []
    for test_ip in ["192.0.2.0", "198.51.100.0", "203.0.113.0"]:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect((test_ip, 80))
        ip_addr = s.getsockname()[0]
        s.close()
        if ip_addr in candidates:
            return ip_addr
        candidates.append(ip_addr)

    return candidates[0]


def get_collection_dir(collection_id):
    return os.path.join(CACHE_DIR, collection_id[:2], collection_id)


def system(args, timeout=None):
    stime = time.time()

    retcode, stdout = proc.run_cmd(args, timeout=timeout)

    d = time.time() - stime

    pub_args = garble_password(args)
    msg = []
    a = msg.append
    a(f"{retcode} {d} {pub_args!r}\n")

    def writemsg():
        return sys.stderr.write("".join(msg))

    if retcode != 0:
        a(stdout)
        a("\n====================\n")

        writemsg()
        lines = ["    " + x for x in stdout[-4096:].split("\n")]
        raise RuntimeError(
            "command failed with returncode {}: {!r}\nLast Output:\n{}".format(
                retcode, pub_args, "\n".join(lines)
            )
        )

    writemsg()


def _get_args(
    writer_options=None,
    language=None,
    zip_only=False,
    login_credentials=None,
    *new_args,
    **kwargs,
):
    args = []

    if login_credentials:
        username, password, domain = (login_credentials.split(":", 3) + [None] * 3)[:3]
        if not username or not password:
            raise ValueError("bad login_credentials")
        args.extend(["--username", username, "--password", password])
        if domain:
            args.extend(["--domain", domain])

    if zip_only:
        return args

    if writer_options:
        args.extend(["--writer-options", writer_options])

    if language:
        args.extend(["--language", language])

    return args


def suggest_filename(metabook_data):
    if not metabook_data:
        return None

    mb = myjson.loads(metabook_data)

    def suggestions():
        yield mb.title
        for a in mb.items:
            yield a.title

    for x in suggestions():
        if x and x.strip():
            return x.strip()


class Commands:
    def statusfile(self):
        host = self.proxy.get_client().host
        port = self.proxy.get_client().port
        return f"qserve://{host}:{port}/{self.jobid}"

    def rpc_makezip(self, params=None):
        def doit(
            metabook_data=None,
            collection_id=None,
            base_url=None,
            writer_options=None,
            *new_args,
            **kwargs,
        ):
            collection_dir = get_collection_dir(collection_id)

            def getpath(p):
                return os.path.join(collection_dir, p)

            zip_path = getpath("collection.zip")
            if os.path.isdir(collection_dir):
                if os.path.exists(zip_path):
                    return
            else:
                os.mkdir(collection_dir)

            metabook_path = getpath("metabook.json")

            args = [
                "mw-zip",
                "-o",
                zip_path,
                "-m",
                metabook_path,
                "--status",
                self.statusfile(),
            ]
            if base_url:
                args.extend(["--config", base_url])
            if writer_options:
                args.extend(["--writer-options", writer_options])

            args.extend(_get_args(zip_only=True, **params))

            if metabook_data:
                f = open(metabook_path, "wb")
                f.write(metabook_data.encode("utf-8"))
                f.close()

            logger.info("running %r", args)
            system(args, timeout=8 * 60.0)

        return doit(**params)

    def rpc_render(self, params=None):
        def doit(metabook_data=None, collection_id=None, _=None, writer=None, **kwargs):
            writer = writer or "rl"
            collection_dir = get_collection_dir(collection_id)

            def getpath(p):
                return os.path.join(collection_dir, p)

            self.qaddw(
                channel="makezip",
                payload={"params": params},
                jobid=f"{collection_id}:makezip",
                timeout=20 * 60,
            )
            outfile = getpath("output.%s" % writer)
            args = [
                "mw-render",
                "-w",
                writer,
                "-c",
                getpath("collection.zip"),
                "-o",
                outfile,
                "--status",
                self.statusfile(),
            ]

            args.extend(_get_args(**params))

            logger.info("running %r", args)
            system(args, timeout=15 * 60.0)
            os.chmod(outfile, 0o644)
            size = os.path.getsize(outfile)
            url = CACHE_URL + f"/{collection_id[:2]}/{collection_id}/output.{writer}"
            return {
                "url": url,
                "size": size,
                "suggested_filename": suggest_filename(metabook_data) or "",
            }

        return doit(**params)


def start_serving_files(cachedir, address, port):
    from gevent.pywsgi import WSGIServer

    cachedir = os.path.abspath(cachedir)
    logger.info(f"serving files from {cachedir!r}")
    s = WSGIServer((address, port), default_app())
    s.start()
    return s


def make_cachedir(cachedir):
    if not os.path.isdir(cachedir):
        os.makedirs(cachedir)
    for i in range(0x100, 0x200):
        p = os.path.join(cachedir, hex(i)[3:])
        if not os.path.isdir(p):
            os.mkdir(p)
            
@route("/cache/:filename#.*#")
def server_static(filename):
    logger.info("serving %r xdfd", filename)
    print("serving", filename, " from ", '/app/cache')
    response = static_file(filename, root='/app/cache', mimetype="application/octet-stream")
    if filename.endswith(".rl"):
        response.headers["Content-Disposition"] = "inline; filename=collection.pdf"
    return response

def main():
    global CACHE_DIR, CACHE_URL
    numgreenlets = 10
    http_address = "0.0.0.0"
    http_port = int(os.environ.get("PORT", 8898))
    serve_files = True
    from mwlib import argv

    opts, args = argv.parse(
        sys.argv[1:],
        "--no-serve-files --serve-files-port= --serve-files-address= --serve-files --cachedir= --url= --numprocs=",
    )
    for o, a in opts:
        if o == "--cachedir":
            # expand relative directories into absolute ones.
            CACHE_DIR = os.path.abspath(a)
        elif o == "--url":
            CACHE_URL = a
        elif o == "--numprocs":
            numgreenlets = int(a)
        elif o == "--no-serve-files":
            serve_files = False
        elif o == "--serve-files-port":
            http_port = int(a)
        elif o == "--serve-files-address":
            http_address = str(a)

    if CACHE_DIR is None:
        sys.exit("nslave: missing --cachedir argument")

    if serve_files:
        wsgi_server = start_serving_files(CACHE_DIR, http_address, http_port)
        port = wsgi_server.socket.getsockname()[1]
        if not CACHE_URL:
            CACHE_URL = f"http://{find_ip()}:{port}/cache"
        logger.info(f"serving files from {CACHE_DIR!r} at url {CACHE_URL}")

    if not CACHE_URL:
        sys.exit("--url option missing")

    make_cachedir(CACHE_DIR)
    # from mwlib.asynchronous import slave

    slave.main(Commands, numgreenlets=numgreenlets, argv=args)


if __name__ == "__main__":
    main()
