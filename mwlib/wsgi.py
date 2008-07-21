#! /usr/bin/env python

"""WSGI dispatcher base class"""

import cgi
import os
import StringIO
import time
import traceback

from mwlib.log import Log

# ==============================================================================

log = Log('mwlib.wsgi')

# ==============================================================================

class Request(object):
    max_post_data_size = 1024*1024
    
    def __init__(self, env):
        self.env = env
        self.method = self.env['REQUEST_METHOD'].upper()
        self.path = self.env.get('PATH_INFO')
        self.query = self.multi2single(cgi.parse_qs(self.env.get('QUERY_STRING', '')))
        if self.method == 'POST':
            self.post_data = self.read_post_data()
        else:
            self.post_data = {}
    
    def multi2single(self, d):
        for key, values in d.items():
            if values:
                d[key] = values[0]
        return d
    
    def read_post_data(self):
        try:
            content_length = int(self.env['CONTENT_LENGTH'])
        except (KeyError, ValueError):
            return {}
        if content_length <= 0:
            return {}
        if content_length > self.max_post_data_size:
            raise RuntimeError('Request data exceeds limit: %d > %d' % (
                content_length, self.max_post_data_size,
            ))
        
        content = self.env['wsgi.input'].read(content_length)
        if len(content) < content_length:
            raise RuntimeError('Expected %d bytes of request data, got %d bytes' % (
                content_length, len(content),
            ))
        
        
        content_type, pdict = cgi.parse_header(self.env.get('CONTENT_TYPE', ''))
        if content_type == 'multipart/form-data':
            post_data = cgi.parse_multipart(StringIO.StringIO(content), pdict)
        else:
            post_data = cgi.parse_qs(content)
        return self.multi2single(post_data)
    

class Response(object):
    def __init__(self, content='', headers=None, status_code=200, status_text='OK'):
        self.content = content
        self.headers = headers or {}
        self.status_code = status_code
        self.status_text = status_text
    
    def finish(self):
        if isinstance(self.content, unicode):
            self.content = self.content.encode('utf-8')
        if isinstance(self.content, str):
            content_length = len(self.content)
        else:
            content_length = os.fstat(self.content.fileno()).st_size
        self.headers['Content-Length'] = '%d' % content_length
            


class Application(object):
    """Subclasses must provide a dispatch() method which gets called with a
    Request object and must return a Response object.
    """
    
    def __call__(self, env, start_response):
        if os.name == 'nt':
            import msvcrt
            fd = env['wsgi.input']
            if hasattr(fd, 'fileno') and fd.fileno() >= 0:
                msvcrt.setmode(fd.fileno(), os.O_BINARY)
        
        start_time = time.time()
        try:
            request = Request(env)
        except Exception, exc:
            log.ERROR('invalid request: %s' % exc)
            traceback.print_exc()
            response = self.http500()
        else:
            try:
                response = self.dispatch(request)
                if not isinstance(response, Response):
                    log.ERROR('invalid result from dispatch(): %r' % response)
                    response = self.http500()
            except Exception, exc:
                response = self.http500(exc)
    
        response.finish()
        start_response(
            '%d %s' % (response.status_code, response.status_text),
            response.headers.items()
        )
        if isinstance(response.content, str):
            yield response.content
        else:
            while True:
                d = response.content.read(0x20000)
                if not d:
                    break
                yield d
        log.info('request took %f s' % (time.time() - start_time))
    
    def http404(self, path):
        log.not_found(path)
        return Response(status_code=404, status_text='Not Found')
    
    def http500(self, exc=None):
        if exc is not None:
            log.SERVER_ERROR(str(exc))
            traceback.print_exc()
        return Response(status_code=500, status_text='Internal Server Error')
    
