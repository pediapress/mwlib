try:
    import simplejson as json
except ImportError:
    import json

import socket

from qs.log import root_logger

logger = root_logger.getChild(__name__)


class RpcClient:
    def __init__(self, host=None, port=None):
        if host is None:
            host = "localhost"
        if port is None:
            port = 14311

        self.host = host
        self.port = port
        self.socket = None

    def _closesocket(self):
        self.writer = self.reader = self.socket = None

    def _get_socket(self):
        logger.info(f"connecting to {self.host}:{self.port}")
        s = self.socket = socket.create_connection((self.host, self.port))
        self.reader = s.makefile("r")
        self.writer = s.makefile("w")

    def send(self, name, **kwargs):
        assert isinstance(name, str)

        if self.socket is None:
            self._get_socket()

        d = json.dumps((name, kwargs)) + "\n"

        def _send():
            logger.info(f"sending {d!r}")
            try:
                self.writer.write(d)
                self.writer.flush()
                line = self.reader.readline()
            except:
                self._closesocket()
                raise

            return json.loads(line)

        try:
            data = _send()
        except Exception:
            self._get_socket()
            data = _send()

        err = data.get("error")
        if err:
            logger.error(f"error: {err}")
            raise RuntimeError(err)
        return data["result"]


class ServerProxy:
    _make_client = RpcClient

    def __init__(self, host=None, port=None, rpc_client=None):
        if rpc_client is None:
            rpc_client = self._make_client(host=host, port=port)
        self._rpc_client = rpc_client

    def __getattr__(self, name):
        def call(**kwargs):
            return self._rpc_client.send(name, **kwargs)

        call.__name__ = name
        self.__dict__[name] = call
        return call

    def get_client(self):
        return self._rpc_client

    def __str__(self):
        return f"ServerProxy({self._rpc_client.host}, {self._rpc_client.port})"
