try:
    import simplejson as json
except ImportError:
    import json
    
import socket

class rpcclient(object):
    def __init__(self, host=None, port=None):
        if host is None:
            host = "localhost"
        if port is None:
            port = 14311
            
        self.host = host
        self.port = port
        self.socket = None
        
    def _getsocket(self):
        s = self.socket = socket.create_connection((self.host, self.port))
        self.reader = s.makefile("r")
        self.writer = s.makefile("w")

    def send(self, name, **kwargs):
        assert isinstance(name, str)
        
        if self.socket is None:
            self._getsocket()

        d = json.dumps((name, kwargs)) + "\n"

        def _send():
            self.writer.write(d)
            self.writer.flush()
            line = self.reader.readline()
            return json.loads(line)

        try:
            data = _send()
        except Exception:
            self._getsocket()
            data = _send()

        
        err = data.get("error")
        if err:
            raise RuntimeError(err)
        return data["result"]
    
class serverproxy(object):
    _make_client = rpcclient
    def __init__(self, host=None, port=None, rpcclient=None):
        if rpcclient is None:
            rpcclient = self._make_client(host=host, port=port)
        self._rpcclient = rpcclient

    def __getattr__(self, name):
        def call(**kwargs):
            return self._rpcclient.send(name, **kwargs)
        call.func_name = name
        self.__dict__[name] = call
        return call
