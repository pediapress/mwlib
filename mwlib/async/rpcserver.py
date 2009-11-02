#! /usr/bin/env python

import traceback

try:
    import simplejson as json
except ImportError:
    import json
    
from gevent import socket
    
def key2str(kwargs):
    r = {}
    for k, v in kwargs.items():
        r[str(k)] = v
    return r

class dispatcher(object):
    def __call__(self, req):
        name, kwargs = req
        kwargs = key2str(kwargs)
        
        assert isinstance(name, basestring), "bad name argument"
        cmdname = str("rpc_"+name)
        m = getattr(self, cmdname, None)
        if not m:
            raise RuntimeError("no such method: %r" % (name, ))
        return m(**kwargs)
    
class request_handler(dispatcher):
    def __init__(self, client=None, clientid=None, **kw):
        self.client = client
        self.clientid = clientid
        super(request_handler, self).__init__(**kw)
        
        
    def shutdown(self):
        super(request_handler, self).shutdown()
        
    
class server(object):
    def __init__(self, port=8080, host="", get_request_handler=None, secret=None):
        self.port = port
        self.host = host
        self.secret = secret
        self.get_request_handler = get_request_handler
        self.sock = socket.tcp_listener((self.host, self.port))
        self.clientcount = 0
        
    def run_forever(self):
        socket.tcp_server(self.sock, self.handle_client)

        
    # def auth():
            # if secret:
            #     random_string = base64.encodestring(os.urandom(16)).strip()
            #     f.write("md5 %s\n" % random_string)
            #     f.flush()
            #     # writer.flush()
            #     line = f.readline()

            #     expected = base64.encodestring(hmac.new(secret, random_string).digest())
            #     if expected.strip() != line.strip():
            #         return
                    # raise RuntimeError("bad auth")
            # else:
            #     writer.write("ok\n")
            #     writer.flush()

    def log(self, msg):
        print msg
        
    def handle_client(self, client):
        try:
            self.clientcount+=1
            clientid = "<%s %s:%s>" % (self.clientcount, client[1][0], client[1][1])
            
            sockfile = client[0].makefile()
            handle_request = self.get_request_handler(client=client, clientid=clientid)
            
            
            self.log("+connect: %s" % (clientid, ))
                     
            while 1:
                line = sockfile.readline()
                # print "got:",  repr(line)
                if not line:
                    break
                
                try:
                    req = json.loads(line)
                except ValueError, err:
                    self.log("+protocol error %s: %s" % (clientid, err))
                    break

                try:
                    d = handle_request(req)                
                    response = json.dumps(dict(result=d))+"\n"
                except Exception, err:
                    response = json.dumps(dict(error=str(err)))+"\n"
                    traceback.print_exc()
                
                sockfile.write(response)
                sockfile.flush()
        except:
            traceback.print_exc()

        finally:
            self.log("-disconnect: %s" % (clientid,))
            client[0].close()
            sockfile.close()
            handle_request.shutdown()
