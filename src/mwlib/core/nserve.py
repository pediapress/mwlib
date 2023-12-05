#! /usr/bin/env python

"""WSGI server interface to mw-render and mw-zip/mw-post"""

import os
import re
import sys
import traceback
import unicodedata
import urllib
from hashlib import sha256
from io import StringIO

import gevent.monkey
import pkg_resources
import six.moves.urllib.error
import six.moves.urllib.parse
import six.moves.urllib.request
from bottle import HTTPResponse, default_app, get, post, request, route, static_file
from gevent import pool, pywsgi
from qs.misc import CallInLoop

from mwlib import _version
from mwlib.asynchronous import rpcclient
from mwlib.metabook import calc_checksum
from mwlib.utilities import log, lrucache
from mwlib.utilities import myjson as json

log = log.root_logger.getChild("mwlib.serve")

if __name__ == "__main__":
    gevent.monkey.patch_all()


class Bunch:
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def __repr__(self):
        return "Bunch({})".format(
            ", ".join([f"{k}={v!r}" for k, v in self.__dict__.items()])
        )


# -- we try to load all writers here but also keep a list of known writers
# -- these writers do not have to be installed on the machine that's running the server
# -- and we also like to speedup the get_writers method

name2writer = {
    "odf": Bunch(
        file_extension="odt",
        name="odf",
        content_type="application/vnd.oasis.opendocument.text",
    ),
    "rl": Bunch(file_extension="pdf", name="rl", content_type="application/pdf"),
    "xhtml": Bunch(file_extension="html", name="xhtml", content_type="text/xml"),
    "xl": Bunch(file_extension="pdf", name="xl", content_type="application/pdf"),
    "zim": Bunch(file_extension="zim", name="zim", content_type="application/zim"),
}


def get_writers():
    for entry_point in pkg_resources.iter_entry_points("mwlib.writers"):
        if entry_point.name in name2writer:
            continue

        try:
            writer = entry_point.load()
            name2writer[entry_point.name] = Bunch(
                name=entry_point.name,
                file_extension=writer.file_extension,
                content_type=writer.content_type,
            )
        except Exception:
            continue

    return name2writer


get_writers()

collection_id_rex = re.compile(r"^[a-f0-9]{16}$")


def make_collection_id(data):
    sio = StringIO()
    sio.write(str(_version.version))
    for key in (
        "base_url",
        "script_extension",
        "login_credentials",
    ):
        sio.write(repr(data.get(key)))
    meta_book = data.get("metabook")
    if meta_book:
        mbobj = json.loads(meta_book)
        sio.write(calc_checksum(mbobj))
        num_articles = len(list(mbobj.articles()))
        base_url = data.get("base_url")
        writer = data.get("writer")
        sys.stdout.write(f"new-collection {num_articles}\t{base_url}\t{writer}\n")

    return sha256(sio.getvalue().encode("utf-8")).hexdigest()[:16]


busy = {}
collid2qserve = lrucache.LRUCache(4000)


class WatchQServe:
    getstats_timeout = 3.0
    sleeptime = 2.0

    def __init__(self, xxx_todo_changeme, busy_data):
        (host, port) = xxx_todo_changeme
        self.host = host
        self.port = port
        self.busy = busy_data
        self.ident = (host, port)
        self.prefix = f"watch: {host}:{port}:"
        self.qserve = None

    def log(self, msg):
        print(self.prefix, msg)

    def _serverproxy(self):
        return rpcclient.ServerProxy(host=self.host, port=self.port)

    def _mark_busy(self, is_busy):
        if is_busy and busy[self.ident] != is_busy:
            self.log(is_busy)

        if not is_busy and busy[self.ident]:
            self.log("resuming operation")

        self.busy[self.ident] = is_busy

    def _sleep(self):
        gevent.sleep(self.sleeptime)

    def _getstats(self):
        if self.qserve is None:
            self.qserve = self._serverproxy()
        try:
            with gevent.Timeout(self.getstats_timeout):
                return self.qserve.getstats()
        except gevent.Timeout:
            self.qserve = None
            raise RuntimeError("timeout calling getstats")
        except BaseException as exc:
            self.qserve = None
            raise RuntimeError(f"error calling getstats: {exc}") from exc

    def _iterate(self):
        try:
            stats = self._getstats()
            numrender = stats.get("busy", {}).get("render", 0)
            if numrender > 10:
                self._mark_busy("system overloaded")
            else:
                self._mark_busy(False)
        except gevent.GreenletExit:
            raise
        except Exception as err:
            self._mark_busy("system down")
            self.log(f"error in WatchQServe: {err}")

    def __call__(self):
        self.busy[self.ident] = True
        while True:
            self._iterate()
            self._sleep()


def choose_idle_qserve():
    import random

    idle = [k for k, v in busy.items() if not v]
    if not idle:
        return None
    return random.choice(idle)  # XXX probably store number of render jobs in busy


@route("/cache/:filename#.*#")
def server_static(filename):
    log.info("serving %r xd", filename)
    print("serving", filename, " from ", '/app/cache')
    response = static_file(filename, root='/app/cache', mimetype="application/octet-stream")
    if filename.endswith(".rl"):
        response.headers["Content-Disposition"] = "inline; filename=collection.pdf"
    return response

@get("<path:re:.*>")
@post("<path:re:.*>")
def dispatch_command(path):
    log.info(f"dispatch_command {path}")
    return Application().dispatch(request)


def get_content_disposition_values(filename, _):
    if isinstance(filename, str):
        filename = six.text_type(filename)

    if filename:
        filename = filename.strip()

    if not filename:
        filename = "collection"

    # see http://code.activestate.com/recipes/251871-latin1-to-ascii-the-unicode-hammer/
    ascii_fn = (
        unicodedata.normalize("NFKD", filename).encode("ASCII", "ignore").decode()
    )
    ascii_fn = re.sub("[ ;:\"',]+", " ", ascii_fn).strip() or "collection"
    ascii_fn = ascii_fn.replace(" ", "-")

    return ascii_fn, filename


def get_content_disposition(filename, ext):
    ascii_fn, utf8_fn = get_content_disposition_values(filename, ext)

    disposition = f"inline; filename={ascii_fn}.{ext}"
    if utf8_fn and utf8_fn != ascii_fn:
        disposition += f";filename*=UTF-8''{urllib.parse.quote(utf8_fn)}.{ext}"
    return disposition


class Application:
    def __init__(self, default_writer="rl"):
        self.default_writer = default_writer
        self.collection_id = None
        self.post_url = None

    def dispatch(self, request):
        try:
            command = request.params["command"]
        except KeyError:
            log.error("no command given in request for url: %r", request.url)
            raise HTTPResponse("no command given", status=400)

        log.info(vars(request.params))

        try:
            method = getattr(self, "do_%s" % command)
        except AttributeError:
            log.error(f"no such command: {command!r}")
            raise HTTPResponse(f"no such command: {command!r}", status=400)
        collection_id = request.params.get("collection_id")
        if not collection_id:
            collection_id = self.new_collection(request.params)
            is_new = True
        else:
            is_new = False
            if not self.check_collection_id(collection_id):
                raise HTTPResponse(status=404)

        try:
            qserve = collid2qserve[collection_id]
        except KeyError:
            qserve = choose_idle_qserve()
            if qserve is None:
                return self.error_response(
                    "system overloaded. please try again later.", queue_full=1
                )
            collid2qserve[collection_id] = qserve

        self.qserve = rpcclient.ServerProxy(host=qserve[0], port=qserve[1])

        try:
            return method(collection_id, request.params, is_new)
        except Exception as exc:
            print(
                "ERROR while dispatching {!r}: {}".format(
                    command,
                    {
                        "collection_id": collection_id,
                        "is_new": is_new,
                        "qserve": qserve,
                    },
                )
            )
            traceback.print_exc()
            if command == "download":
                raise exc

            return self.error_response(f"error executing command {command!r}: {exc}")

    def error_response(self, error, **kw):
        return dict(error=error, **kw)

    def check_collection_id(self, collection_id):
        """Return True iff collection with given ID exists"""

        if not collection_id or not collection_id_rex.match(collection_id):
            return False
        return True

    def new_collection(self, post_data):
        collection_id = make_collection_id(post_data)
        return collection_id

    def is_good_baseurl(self, url):
        netloc = six.moves.urllib.parse.urlparse(url)[1].split(":")[0].lower()
        if (
            netloc == "localhost"
            or netloc.startswith("127.0.")
            or netloc.startswith("192.168.")
        ):
            return False
        return True

    def _get_params(self, post_data, collection_id):
        get = post_data.get
        params = Bunch()
        params.__dict__ = {
            "metabook_data": get("metabook"),
            "writer": get("writer", self.default_writer),
            "base_url": get("base_url"),
            "writer_options": get("writer_options", ""),
            "login_credentials": get("login_credentials", ""),
            "force_render": bool(get("force_render")),
            "script_extension": get("script_extension", ""),
            "pod_api_url": post_data.get("pod_api_url", ""),
            "language": get("language", ""),
        }

        params.collection_id = collection_id

        return params

    def do_render(self, collection_id, post_data, is_new=False):
        params = self._get_params(post_data, collection_id=collection_id)
        metabook_data = params.metabook_data
        log.info(f"render {collection_id} {metabook_data}")
        base_url = params.base_url
        writer = params.writer

        if writer not in name2writer:
            return self.error_response("unknown writer %r" % writer)

        if is_new and not metabook_data:
            return self.error_response(
                "POST argument metabook or collection_id required"
            )
        if not is_new and metabook_data:
            return self.error_response(
                "Specify either metabook or collection_id, not both"
            )

        if base_url and not self.is_good_baseurl(base_url):
            log.bad(f"bad base_url: {base_url!r}")
            return self.error_response(
                "bad base_url {!r}. check your $wgServer and $wgScriptPath variables. localhost, 192.168.*.* and 127.0.*.* are not allowed.".format(
                    base_url
                )
            )

        log.info(f"render {collection_id} {writer}")

        response = {
            "collection_id": collection_id,
            "writer": writer,
            "is_cached": False,
        }

        self.qserve.qadd(
            channel="makezip",
            payload={"params": params.__dict__},
            jobid=f"{collection_id}:makezip",
            timeout=20 * 60,
        )

        self.qserve.qadd(
            channel="render",
            payload={"params": params.__dict__},
            jobid=f"{collection_id}:render-{writer}",
            timeout=20 * 60,
        )

        return response

    def _process_and_return_finished_state(self, res, name_writer, retval):
        more = {}
        try:
            if res["result"]:
                more["url"] = res["result"]["url"]
                more["content_length"] = res["result"]["size"]
                more["suggested_filename"] = res["result"].get("suggested_filename", "")
        except KeyError:
            pass
        if name_writer.content_type:
            more["content_type"] = name_writer.content_type
        if name_writer.file_extension:
            more["content_disposition"] = get_content_disposition(
                more.get("suggested_filename", None), name_writer.file_extension
            )
        return retval(state="finished", **more)

    def do_render_status(self, collection_id, post_data, is_new=False):
        if is_new:
            return self.error_response("POST argument required: collection_id")

        def retval(**kw):
            return dict(collection_id=collection_id, writer=writer, **kw)

        writer = post_data.get("writer", self.default_writer)
        name_writer = name2writer[writer]

        jobid = f"{collection_id}:render-{writer}"

        res = self.qserve.qinfo(jobid=jobid) or {}
        info = res.get("info", {})
        done = res.get("done", False)
        error = res.get("error", None)

        if error:
            return retval(state="failed", error=error)

        if done:
            return self._process_and_return_finished_state(res, name_writer, retval)

        if not info:
            jobid = f"{collection_id}:makezip"
            res = self.qserve.qinfo(jobid=jobid) or {}

            done = res.get("done", False)
            if not done:
                info = res.get("info", {})
            else:
                info = {"status": "data fetched. waiting for render process.."}

        return retval(state="progress", status=info)

    def do_download(self, collection_id, post_data, is_new=False):
        if is_new:
            return self.error_response("POST argument required: collection_id")

        writer = post_data.get("writer", self.default_writer)
        name_writer = name2writer[writer]

        jobid = f"{collection_id}:render-{writer}"
        res = self.qserve.qinfo(jobid=jobid) or {}
        download_url = res["result"]["url"]

        print("fetching", download_url)
        downloaded_file = six.moves.urllib.request.urlopen(download_url).info()
        info = downloaded_file.info()

        header = {}

        for header in ("Content-Length",):
            value = info.getheader(header)
            if value:
                print("copy header:", header, value)
                header[header] = value

        if name_writer.content_type:
            header["Content-Type"] = name_writer.content_type

        if name_writer.file_extension:
            header["Content-Disposition"] = "inline; filename=collection.%s" % (
                name_writer.file_extension.encode("utf-8", "ignore")
            )

        def readdata():
            while True:
                data = downloaded_file.read(4096)
                if not data:
                    break
                yield data

        return HTTPResponse(output=readdata(), header=header)

    def do_zip_post(self, collection_id, post_data, _):
        params = self._get_params(post_data, collection_id=collection_id)

        try:
            post_data["metabook"]
        except KeyError as exc:
            return self.error_response("POST argument required: %s" % exc)

        pod_api_url = params.pod_api_url
        if pod_api_url:
            result = json.loads(
                six.text_type(
                    six.moves.urllib.request.urlopen(
                        pod_api_url, data="any".encode("utf-8")
                    ).read(),
                    "utf-8",
                )
            )
            post_url = result["post_url"].encode("utf-8")
            response = {
                "state": "ok",
                "redirect_url": result["redirect_url"].encode("utf-8"),
            }
        else:
            try:
                post_url = post_data["post_url"]
            except KeyError:
                return self.error_response("POST argument required: post_url")
            response = {"state": "ok"}

        log.info(f"zip_post {collection_id} {pod_api_url}")
        params.post_url = post_url

        self.qserve.qadd(
            channel="post",
            payload={"params": params.__dict__},
            timeout=20 * 60,
        )
        return response


def _parse_qs(q_serve):
    for i, arg in enumerate(q_serve):
        if ":" in arg:
            host, port = arg.split(":", 1)
            port = int(port)
            q_serve[i] = (host, port)
        else:
            q_serve[i] = (arg, 14311)


def main():
    from mwlib import argv

    opts, args = argv.parse(
        sys.argv[1:], "--disable-all-writers --qserve= --port= -i= --interface="
    )
    q_serve = []
    port = int(os.environ.get("PORT", 8899))
    interface = "0.0.0.0"
    for opt, arg in opts:
        if opt == "--port":
            port = int(arg)
        elif opt == "--qserve":
            q_serve.append(arg)
        elif opt == "--disable-all-writers":
            name2writer.clear()
        elif opt in ("-i", "--interface"):
            interface = arg

    print("using the following writers", sorted(name2writer.keys()))

    q_serve += args

    if not q_serve:
        q_serve.append("localhost:14311")

    _parse_qs(q_serve)

    address = interface, port
    server = pywsgi.WSGIServer(address, default_app())

    watchers = pool.Pool()
    for watcher in q_serve:
        watchers.spawn(CallInLoop(5.0, WatchQServe(watcher, busy)))

    try:
        print("listening on %s:%d" % address)
        server.serve_forever()
    except KeyboardInterrupt:
        server.stop()
        print("bye.")


if __name__ == "__main__":
    main()
