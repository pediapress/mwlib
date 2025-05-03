#! /usr/bin/env python

import traceback

try:
    import simplejson as json
except ImportError:
    import json

from gevent import (
    Greenlet,
    GreenletExit,
    getcurrent,
    pool,
    queue,
    spawn,
)
from gevent import (
    server as gserver,
)

from qs.log import root_logger

logger = root_logger.getChild(__name__)


def key2str(kwargs):
    r = {}
    for k, v in list(kwargs.items()):
        r[str(k)] = v
    return r


class Dispatcher:
    def __call__(self, req):
        name, kwargs = req
        kwargs = key2str(kwargs)

        assert isinstance(name, str), "bad name argument"
        cmd_name = str("rpc_" + name)
        m = getattr(self, cmd_name, None)
        if not m:
            raise RuntimeError("no such method: %r" % (cmd_name,))
        return m(**kwargs)


class RequestHandler(Dispatcher):
    def __init__(self, client=None, client_id=None, **kw):
        self.client = client
        self.client_id = client_id
        super(RequestHandler, self).__init__(**kw)

    def shutdown(self):
        super(RequestHandler, self).shutdown()


class ClientGreenlet(Greenlet):
    client_id = None
    status = ""

    def __str__(self):
        return "<%s: %s>" % (self.client_id, self.status)

    def __repr__(self):
        return "<Client %s>" % self.client_id


class Server:
    def __init__(
        self, port=8080, host="", get_request_handler=None, secret=None, is_allowed=None
    ):
        self.port = port
        self.host = host
        self.secret = secret
        self.get_request_handler = get_request_handler
        self.pool = pool.Pool(1024, ClientGreenlet)
        self.stream_server = gserver.StreamServer(
            (host, port), self.handle_client, spawn=self.pool.spawn
        )
        if hasattr(self.stream_server, "pre_start"):
            self.stream_server.pre_start()
        else:
            self.stream_server.init_socket()  # gevent >= 1.0b1
        self.client_count = 0

        if is_allowed is None:
            self.is_allowed = lambda x: True
        else:
            self.is_allowed = is_allowed

    def run_forever(self):
        self.stream_server.serve_forever()

    def log(self, msg):
        logger.info(msg)

    def handle_client(self, sock, addr):
        if not self.is_allowed(addr[0]):
            self.log("+DENY %r" % (addr,))
            sock.close()
            return
        sock_file = None
        current = getcurrent()
        try:
            self.client_count += 1
            clientid = "<%s %s:%s>" % (self.client_count, addr[0], addr[1])
            current.clientid = clientid
            sock_file = sock.makefile("rw")
            lineq = queue.Queue()

            def readlines():
                while 1:
                    try:
                        line = sock_file.readline()
                    except Exception as e:
                        self.log(f"error reading socket: {e}")
                        break
                    lineq.put(line)
                    if not line:
                        break

            readgr = spawn(readlines)
            readgr.link(lambda _: current.kill())
            current.link(lambda _: readgr.kill())
            handle_request = self.get_request_handler(
                client=(sock, addr), clientid=clientid
            )

            self.log("+connect: %s" % (clientid,))

            while 1:
                current.status = "idle"
                line = lineq.get()
                if not line:
                    break

                try:
                    req = json.loads(line)
                except ValueError as err:
                    self.log(f"+protocol error {clientid}: {err}")
                    break

                current.status = "dispatching: %s" % line[:-1]
                try:
                    d = handle_request(req)
                    response = json.dumps({"result": d}) + "\n"
                except GreenletExit:
                    raise
                except Exception as err:
                    response = json.dumps({"error": str(err)}) + "\n"
                    logger.exception(err)

                current.status = "sending response: %s" % response[:-1]
                sock_file.write(response)
                sock_file.flush()
        except GreenletExit:
            raise
        except Exception:
            logger.exception("error handling client")

        finally:
            current.status = "dead"
            # self.log("-disconnect: %s" % (clientid,))
            sock.close()
            if sock_file is not None:
                sock_file.close()
            handle_request.shutdown()
