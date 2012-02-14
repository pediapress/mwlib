#! /usr/bin/env python

from gevent import monkey
monkey.patch_all()

import os, sys, time, socket

cachedir = None
cacheurl = None

from mwlib.async import proc
from mwlib.utils import garble_password


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
    return os.path.join(cachedir, collection_id[:2], collection_id)


def system(args, timeout=None):
    stime = time.time()

    retcode, stdout = proc.run_cmd(args, timeout=timeout)

    d = time.time() - stime

    pub_args = garble_password(args)
    msg = []
    a = msg.append
    a("%s %s %r\n" % (retcode, d, pub_args))

    writemsg = lambda: sys.stderr.write("".join(msg))

    if retcode != 0:
        a(stdout)
        a("\n====================\n")

        writemsg()
        lines = ["    " + x for x in stdout[-4096:].split("\n")]
        raise RuntimeError("command failed with returncode %s: %r\nLast Output:\n%s" % (retcode, pub_args,  "\n".join(lines)))

    writemsg()


def _get_args(writer_options=None,
              template_blacklist=None,
              template_exclusion_category=None,
              print_template_prefix=None,
              print_template_pattern=None,
              language=None,
              zip_only=False,
              login_credentials=None,
              **kw):

    args = []

    if template_blacklist:
        args.extend(['--template-blacklist', template_blacklist])
    if template_exclusion_category:
        args.extend(['--template-exclusion-category', template_exclusion_category])
    if print_template_prefix:
        args.extend(['--print-template-prefix', print_template_prefix])
    if print_template_pattern:
        args.extend(['--print-template-pattern', print_template_pattern])

    if login_credentials:
        username, password, domain = (login_credentials.split(":", 3) + [None] * 3)[:3]
        assert username and password, "bad login_credentials"
        args.extend(["--username", username, "--password", password])
        if domain:
            args.extend(["--domain", domain])

    if zip_only:
        return args

    if writer_options:
        args.extend(['--writer-options', writer_options])

    if language:
        args.extend(['--language', language])

    return args


class commands(object):
    def statusfile(self):
        host = self.proxy._rpcclient.host
        port = self.proxy._rpcclient.port
        return 'qserve://%s:%s/%s' % (host, port, self.jobid)

    def rpc_makezip(self, params=None):
        def doit(metabook_data=None, collection_id=None, base_url=None, **kw):
            dir = get_collection_dir(collection_id)

            def getpath(p):
                return os.path.join(dir, p)

            zip_path = getpath("collection.zip")
            if os.path.isdir(dir):
                if os.path.exists(zip_path):
                    return
            else:
                os.mkdir(dir)

            metabook_path = getpath("metabook.json")

            args = ["mw-zip", "-o", zip_path, "-m", metabook_path, "--status", self.statusfile()]
            if base_url:
                args.extend(['--config', base_url])

            args.extend(_get_args(zip_only=True, **params))

            if metabook_data:
                f = open(metabook_path, 'wb')
                f.write(metabook_data)
                f.close()

            system(args, timeout=8 * 60.0)

        return doit(**params)

    def rpc_render(self, params=None):
        def doit(metabook_data=None, collection_id=None, base_url=None, writer=None, **kw):
            writer = writer or "rl"
            dir = get_collection_dir(collection_id)

            def getpath(p):
                return os.path.join(dir, p)

            self.qaddw(channel="makezip", payload=dict(params=params), jobid="%s:makezip" % (collection_id, ), timeout=20 * 60)
            outfile = getpath("output.%s" % writer)
            args = ["mw-render",  "-w",  writer, "-c", getpath("collection.zip"), "-o", outfile,  "--status", self.statusfile()]

            args.extend(_get_args(**params))

            system(args, timeout=15 * 60.0)
            os.chmod(outfile, 0644)
            size = os.path.getsize(outfile)
            url = cacheurl + "/%s/%s/output.%s" % (collection_id[:2], collection_id, writer)
            return dict(url=url, size=size)

        return doit(**params)


def start_serving_files(cachedir, port):
    from gevent.pywsgi import WSGIServer
    from bottle import route, static_file, default_app
    cachedir = os.path.abspath(cachedir)

    @route('/cache/:filename#.*#')
    def server_static(filename):
        response = static_file(filename, root=cachedir, mimetype="application/octet-stream")
        if filename.endswith(".rl"):
            response.headers["Content-Disposition"] = "inline; filename=collection.pdf"
        return response
    s = WSGIServer(("", port), default_app())
    s.start()
    return s


def make_cachedir(cachedir):
    if not os.path.isdir(cachedir):
        os.makedirs(cachedir)
    for i in range(0x100, 0x200):
        p = os.path.join(cachedir, hex(i)[3:])
        if not os.path.isdir(p):
            os.mkdir(p)


def main():
    global cachedir, cacheurl
    numgreenlets = 10
    http_port = 8898
    serve_files = True
    from mwlib import argv
    opts, args = argv.parse(sys.argv[1:], "--no-serve-files --serve-files-port= --serve-files --cachedir= --url= --numprocs=")
    for o, a in opts:
        if o == "--cachedir":
            cachedir = a
        elif o == "--url":
            cacheurl = a
        elif o == "--numprocs":
            numgreenlets = int(a)
        elif o == "--no-serve-files":
            serve_files = False
        elif o == "--serve-files-port":
            http_port = int(a)

    if cachedir is None:
        sys.exit("nslave.py: missing --cachedir argument")

    if serve_files:
        wsgi_server = start_serving_files(cachedir, http_port)
        port = wsgi_server.socket.getsockname()[1]
        if not cacheurl:
            cacheurl = "http://%s:%s/cache" % (find_ip(), port)
        print "serving files from %r at url %s" % (cachedir, cacheurl)

    if not cacheurl:
        sys.exit("--url option missing")

    make_cachedir(cachedir)
    from mwlib.async import slave
    slave.main(commands, numgreenlets=numgreenlets, argv=args)

if __name__ == "__main__":
    main()
