#! /usr/bin/env python

import getpass
import os
import socket
import sys
import traceback
from io import StringIO

import gevent
import gevent.monkey
from qs.rpcclient import ServerProxy

from mwlib import argv
from mwlib.asynchronous import slave
from mwlib.podclient import PODClient
from mwlib.status import Status
from mwlib.utils import send_mail

cachedir = "cache"
gevent.monkey.patch_all()


def get_collection_dir(collection_id):
    return os.path.join(cachedir, collection_id[:2], collection_id)


def _get_args(writer_options=None, language=None, zip_only=False):
    args = []

    if zip_only:
        return args

    if writer_options:
        args.extend(["--writer-options", writer_options])

    if language:
        args.extend(["--language", language])

    return args


def uploadfile(ipath, posturl, file_handler=None):
    if file_handler is None:
        file_handler = open(ipath, "rb")

    podclient = PODClient(posturl)

    status = Status(podclient=podclient)

    try:
        status(status="uploading", progress=0)
        podclient.streaming_post_zipfile(ipath, file_handler)
        status(status="finished", progress=100)
    except Exception as err:
        status(status="error")
        raise err


def report_upload_status(posturl, file_handler):
    podclient = PODClient(posturl)

    file_handler.seek(0, 2)
    size = file_handler.tell()
    file_handler.seek(0, 0)

    status = Status(podclient=podclient)
    numdots = 0

    last = None
    while True:
        cur = file_handler.tell()
        if cur != last:
            if cur == size:
                break
            numdots = (numdots + 1) % 10
            status("uploading" + "." * numdots, progress=100.0 * cur / size)
            last = cur

        else:
            gevent.sleep(0.1)


def report_mwzip_status(posturl, jobid, host, port):
    podclient = PODClient(posturl)
    status = Status(podclient=podclient)

    server_proxy = ServerProxy(host, port)

    last = {}
    while True:
        res = server_proxy.qinfo(jobid=jobid) or {}

        done = res.get("done", False)
        if done:
            break
        info = res.get("info", {})
        if info != last:
            status(status=info.get("status", "fetching"),
                   progress=info.get("progress", 0.0))
            last = info
        else:
            gevent.sleep(0.5)


def report_exception(posturl, xxx_todo_changeme):
    (_, err, _) = xxx_todo_changeme
    print("reporting error to", posturl, repr(str(err)[:50]))

    podclient = PODClient(posturl)
    podclient.post_status(error=str(err))


mailfrom = f"{getpass.getuser()}@{socket.gethostname()}"


def report_exception_mail(subject, exc_info):
    mailto = os.environ.get("MAILTO")
    if not mailto:
        print("MAILTO not set. not sending email.")
        return

    print("sending mail to", mailto)

    f = StringIO.StringIO()
    traceback.print_exception(*exc_info, file=f)

    send_mail(mailfrom, [mailto], subject, f.getvalue())


class Commands:
    def statusfile(self):
        host = self.proxy._rpcclient.host
        port = self.proxy._rpcclient.port
        return f"qserve://{host}:{port}/{self.jobid}"

    def rpc_post(self, params):
        post_url = params["post_url"]

        def _doit(metabook_data=None, collection_id=None, base_url=None,
                  post_url=None, **kw):
            directory = get_collection_dir(collection_id)

            def getpath(path):
                return os.path.join(directory, path)

            jobid = f"{collection_id}:makezip"
            greenlet_for_status = gevent.spawn_later(
                0.2,
                report_mwzip_status,
                post_url,
                jobid,
                self.proxy._rpcclient.host,
                self.proxy._rpcclient.port,
            )

            try:
                self.qaddw(
                    channel="makezip", payload={"params": params},
                    jobid=jobid, timeout=20 * 60
                )
            finally:
                greenlet_for_status.kill()
                del greenlet_for_status

            ipath = getpath("collection.zip")

            with open(ipath, "wb") as file_handler:

                greenlet_for_upload = gevent.spawn(report_upload_status, post_url, file_handler)
                try:
                    uploadfile(ipath, post_url, file_handler)
                finally:
                    greenlet_for_upload.kill()
                    del greenlet_for_upload

        def doit(**params):
            try:
                return _doit(**params)
            except Exception:
                exc_info = sys.exc_info()
                gevent.spawn(report_exception, post_url, exc_info)
                gevent.spawn(report_exception_mail, "zip upload failed",
                             exc_info)
                del exc_info
                raise

        return doit(**params)


def main():
    global cachedir

    opts, args = argv.parse(sys.argv[1:], "--cachedir=")
    for o, a in opts:
        if o == "--cachedir":
            cachedir = a

    slave.main(Commands, numgreenlets=32, argv=args)


if __name__ == "__main__":
    main()
