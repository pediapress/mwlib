#! /usr/bin/env python

"""WSGI server interface to mw-render and mw-zip/mw-post"""
import gevent.monkey
gevent.monkey.patch_socket()
# import setproctitle
# setproctitle.setproctitle("nserve")
from geventutil import worker

import sys
import os
import re
import StringIO
import urllib2
import urlparse
import traceback

from hashlib import md5

from mwlib import myjson as json

from webob import Request, Response

from mwlib import log, utils, _version
from mwlib.metabook import calc_checksum

from mwlib.async import rpcclient

log = log.Log('mwlib.serve')

class bunch(object):
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def __repr__(self):
        return "bunch(%s)" % (", ".join(["%s=%r" % (k, v) for k, v in self.__dict__.items()]), )

    
# -- we try to load all writers here but also keep a list of known writers
# -- these writers do not have to be installed on the machine that's running the server
# -- and we also like to speedup the get_writers method
    
name2writer = {'rl': bunch(file_extension='pdf', name='rl', content_type='application/pdf'),
               'xhtml': bunch(file_extension='html', name='xhtml', content_type='text/xml'),
               'xl': bunch(file_extension='pdf', name='xl', content_type='application/pdf'),
               'odf': bunch(file_extension='odt', name='odf', content_type='application/vnd.oasis.opendocument.text')}

def get_writers(name2writer):
    import pkg_resources
    
    for entry_point in pkg_resources.iter_entry_points('mwlib.writers'):
        if entry_point.name in name2writer:
            continue
        
        try:
            writer = entry_point.load()
            name2writer[entry_point.name] = bunch(name=entry_point.name,
                                                  file_extension=writer.file_extension,
                                                  content_type=writer.content_type)
        except Exception:
            continue

    return name2writer

get_writers(name2writer)

class colldir(object):
    def __init__(self, path):
        self.dir = os.path.abspath(path)

    def getpath(self, p):
        return os.path.join(self.dir, p)

collection_id_rex = re.compile(r'^[a-z0-9]{16}$')

def make_collection_id(data):
    sio = StringIO.StringIO()
    for key in (
        _version.version,
        'base_url',
        'script_extension',
        'template_blacklist',
        'template_exclusion_category',
        'print_template_prefix',
        'print_template_pattern',
        'login_credentials',
    ):
        sio.write(repr(data.get(key)))
    mb = data.get('metabook')
    if mb:
        if isinstance(mb, str):
            mb = unicode(mb, 'utf-8')
        mbobj = json.loads(mb)
        sio.write(calc_checksum(mbobj))
        num_articles = len(list(mbobj.articles()))
        sys.stdout.write("new-collection %s\t%r\t%r\n" % (num_articles, data.get("base_url"), data.get("writer")))
        
    return md5(sio.getvalue()).hexdigest()[:16]


def json_response(fn):
    """Decorator wrapping result of decorated function in JSON response"""
    
    def wrapper(*args, **kwargs):
        result = fn(*args, **kwargs)
        if isinstance(result, Response):
            return result
        return Response(json.dumps(result), content_type='application/json')
    return wrapper

from mwlib import lrucache
busy=dict()
collid2qserve = lrucache.lrucache(4000)

    

def wait_idle((host, port),  busy):
    ident = (host, port)
    busy[ident] = True
    numerrors = 0
    
    qserve = rpcclient.serverproxy(host=host, port=port)
    while 1:
        try:
            stats = qserve.getstats()
            numerrors = 0
            
            numrender = stats.get("busy",  {}).get("render", 0)

            if numrender>10:
                if not busy[ident]:
                    print "SYSTEM OVERLOADED on %r" % (ident, )
                    busy[ident] = True
            else:
                if busy[ident]:
                    print "RESUMING OPERATION on %r" % (ident, )
                    busy[ident] = False
                    
        except Exception, err:
            numerrors+=1
                
            try:
                if numerrors==2:
                    busy[ident]=True
                    print "SYTEM DOWN: %r" % (ident, )
                print "ERROR in wait_idle for %r:%s" % (ident, err)
            except:
                pass
        finally:
            gevent.sleep(2)
            
def choose_idle_qserve():
    import random
    idle = [k for k, v in busy.items() if not v]
    if not idle:
        return None
    return random.choice(idle) # XXX probably store number of render jobs in busy


class Application(object):
    def __init__(self,
                 cache_dir="cache",
                 default_writer='rl',
                 report_from_mail=None,
                 report_recipients=None):

        self.cache_dir = cache_dir
            
        self.default_writer = default_writer
        self.report_from_mail = report_from_mail
        self.report_recipients = report_recipients

        # self.qserve = rpcclient.serverproxy()
        
    def __call__(self, environ, start_response):
        request = Request(environ)

        # if request.method != 'POST':
        #     response = Response(status=405)
        # else:
        response = self.dispatch(request)

        return response(environ, start_response)
    
    def dispatch(self, request):
        try:
            command = request.params['command']
        except KeyError:
            log.error("no command given")
            return Response(body="no command given", status=400)

        try:
            method = getattr(self, 'do_%s' % command)
        except AttributeError:
            log.error("no such command: %r" %(command, ))
            return Response(body="no such command: %r" % (command, ), status=400)

        collection_id = request.params.get('collection_id')
        if not collection_id:
            collection_id = self.new_collection(request.params)
            is_new = True
        else:
            is_new = False

        try:
            qserve = collid2qserve[collection_id]
        except KeyError:
            qserve = choose_idle_qserve()
            if qserve is None:
                return self.error_response("system overloaded. please try again later.", queue_full=1)
            collid2qserve[collection_id] = qserve
            
        self.qserve = rpcclient.serverproxy(host=qserve[0], port=qserve[1])
            
        if not self.check_collection_id(collection_id):
            return Response(status=404)

        try:
            return method(collection_id, request.params, is_new)
        except Exception, exc:
            print "ERROR while dispatching %r: %s" % (command, dict(collection_id=collection_id, is_new=is_new, qserve=qserve))
            traceback.print_exc()
            self.send_report_mail('exception', command=command)
            if command=="download":
                raise exc

            return self.error_response('error executing command %r: %s' % (
                    command, exc,))
    
    @json_response
    def error_response(self, error, **kw):
        if isinstance(error, str):
            error = unicode(error, 'utf-8', 'ignore')
        elif not isinstance(error, unicode):
            error = unicode(repr(error), 'ascii')
        return dict(error=error, **kw)
    
    def send_report_mail(self, subject, **kwargs):
        if not (self.report_from_mail and self.report_recipients):
            return
        utils.report(
            system='mwlib.serve',
            subject=subject,
            from_email=self.report_from_mail,
            mail_recipients=self.report_recipients,
            **kwargs
        )
    
    def get_collection_dir(self, collection_id):
        return os.path.join(self.cache_dir, collection_id[:2], collection_id)
    
    def check_collection_id(self, collection_id):
        """Return True iff collection with given ID exists"""
        
        if not collection_id or not collection_id_rex.match(collection_id):
            return False
        return True
    
    def new_collection(self, post_data):
        collection_id = make_collection_id(post_data)
        return collection_id
    
    def get_path(self, collection_id, filename, ext=None):
        p = os.path.join(self.get_collection_dir(collection_id), filename)
        if ext is not None:
            p += '.' + ext[:10]
        return p

    def is_good_baseurl(self, url):
        netloc = urlparse.urlparse(url)[1].lower()
        if netloc.startswith("localhost") or netloc.startswith("127.0") or netloc.startswith("192.168"):
            return False
        return True
    


    def _get_params(self, post_data,  collection_id):
        g = post_data.get
        params = bunch()
        params.__dict__ = dict(
            metabook_data = g('metabook'), 
            writer = g('writer', self.default_writer), 
            base_url = g('base_url'), 
            writer_options = g('writer_options', ''), 
            template_blacklist = g('template_blacklist', ''), 
            template_exclusion_category = g('template_exclusion_category', ''), 
            print_template_prefix = g('print_template_prefix', ''), 
            print_template_pattern = g('print_template_pattern', ''), 
            login_credentials = g('login_credentials', ''), 
            force_render = bool(g('force_render')), 
            script_extension = g('script_extension', ''),
            pod_api_url = post_data.get('pod_api_url', ''), 
            language = g('language', ''))
        
        params.collection_id = collection_id
        
        return params
    
    
    @json_response
    def do_render(self, collection_id, post_data, is_new=False):
        params = self._get_params(post_data,  collection_id=collection_id)
        metabook_data = params.metabook_data
        base_url = params.base_url
        writer = params.writer
        force_render = params.force_render

        # if busy:
        #     return self.error_response("system overloaded. please try again later.", queue_full=1)
        
        if writer not in name2writer:
            return self.error_response("unknown writer %r" % writer)
    
        if is_new and not metabook_data:
            return self.error_response('POST argument metabook or collection_id required')
        if not is_new and metabook_data:
            return self.error_response('Specify either metabook or collection_id, not both')
        
        if base_url and not self.is_good_baseurl(base_url):
            log.bad("bad base_url: %r" % (base_url, ))
            return self.error_response("bad base_url %r. check your $wgServer and $wgScriptPath variables" % (base_url, ))
        
        log.info('render %s %s' % (collection_id, writer))
        
        response = {
            'collection_id': collection_id,
            'writer': writer,
            'is_cached': False,
        }

        self.qserve.qadd(channel="makezip", payload=dict(params=params.__dict__), jobid="%s:makezip" % (collection_id, ), timeout=20*60)
        
        self.qserve.qadd(channel="render", payload=dict(params=params.__dict__), 
                         jobid="%s:render-%s" % (collection_id, writer),  timeout=20*60)

        return response
    
    @json_response
    def do_render_status(self, collection_id, post_data, is_new=False):
        if is_new:
            return self.error_response('POST argument required: collection_id')

        def retval(**kw):
            return dict(collection_id=collection_id, writer=writer, **kw)
        
        writer = post_data.get('writer', self.default_writer)
        w=name2writer[writer]
        
        jobid="%s:render-%s" % (collection_id, writer)
        
        res = self.qserve.qinfo(jobid=jobid) or {}
        info = res.get("info", {})
        done = res.get("done", False)
        error = res.get("error", None)

        if error:    
            return retval(state="failed", error=error)

        if done:
            more = dict()
            
            try:
                if res["result"]:
                    more["url"] = res["result"]["url"]
                    more["content_length"] = res["result"]["size"]
            except KeyError:
                pass
            
            if w.content_type:
                more["content_type"] = w.content_type

            if w.file_extension:
                more["content_disposition"] = 'inline; filename=collection.%s' % (w.file_extension.encode('utf-8', 'ignore'))
            
            return retval(state="finished", **more)

        if not info:
            jobid="%s:makezip" % (collection_id,)
            res = self.qserve.qinfo(jobid=jobid) or {}
            
            done = res.get("done", False)
            if not done:
                info = res.get("info", {})
            else:
                info = dict(status="data fetched. waiting for render process..")
        
        return retval(state="progress", status=info)
    
    @json_response
    def do_render_kill(self, collection_id, post_data, is_new=False):
        if is_new:
            return self.error_response('POST argument required: collection_id')

        writer = post_data.get('writer', self.default_writer)
        
        log.info('render_kill %s %s' % (collection_id, writer))

        killed = False
        # pid_path = self.get_path(collection_id, self.pid_filename, writer)
        # try:
        #     pid = int(open(pid_path, 'rb').read())
        #     os.kill(pid, signal.SIGKILL)
        #     killed = True
        # except (OSError, ValueError, IOError):
        #     pass
        return {
            'collection_id': collection_id,
            'writer': writer,
            'killed': killed,
        }
        
    def do_download(self, collection_id, post_data, is_new=False):
        if is_new:
            return self.error_response('POST argument required: collection_id')

        writer = post_data.get('writer', self.default_writer)
        w=name2writer[writer]


        
        jobid="%s:render-%s" % (collection_id, writer)        
        res = self.qserve.qinfo(jobid=jobid) or {}
        download_url = res["result"]["url"]

        print "fetching", download_url
        f = urllib2.urlopen(download_url)
        info = f.info()

        response = Response()

        for h in ("Content-Length",): # "Content-Type", "Content-Disposition"):            
            v = info.getheader(h)
            if v:
                print "copy header:", h, v
                response.headers[h] = v

        if w.content_type:
            response.content_type = w.content_type
                
        if w.file_extension:
            response.headers['Content-Disposition'] = 'inline; filename=collection.%s' % (w.file_extension.encode('utf-8', 'ignore'))
        
                
        def readdata():
            while 1:
                d = f.read(4096)
                if not d:
                    break
                yield d
                
        response.app_iter = readdata()
        return response
    
        
        
        
        
        try:
            log.info('download %s %s' % (collection_id, writer))

            redir = os.environ.get("NSERVE_REDIRECT")
            if redir:
                response = Response()
                response.status = 301
                url = "%s/%s/%s/output.%s" % (redir, collection_id[:2], collection_id, writer)
                print "REDIRECT:", url
                response.location = url
                return response


            if 1:
                response=Response()
                response.headers["X-Accel-Redirect"] = "/%s/%s/output.%s" % (collection_id[:2], collection_id, writer)


                if w.content_type:
                    response.content_type = w.content_type
                
                if w.file_extension:
                    response.headers['Content-Disposition'] = 'inline; filename=collection.%s' % (w.file_extension.encode('utf-8', 'ignore'))

                return response
            
            output_path = self.get_path(collection_id, "output", writer)
            os.utime(output_path, None)
            
            data = open(output_path, "rb").read()
            
            response = Response(data, content_length=len(data))
            
            if w.content_type:
                response.content_type = w.content_type
                
            if w.file_extension:
                response.headers['Content-Disposition'] = 'inline; filename=collection.%s' % (
                    w.file_extension.encode('utf-8', 'ignore'))
            
            return response
        except Exception, exc:
            log.ERROR('exception in do_download(): %r' % exc)
            return Response(status=500)
    
    @json_response
    def do_zip_post(self, collection_id, post_data, is_new=False):
        params = self._get_params(post_data, collection_id=collection_id)
        
        try:
            metabook_data = post_data['metabook']
        except KeyError, exc:
            return self.error_response('POST argument required: %s' % exc)
        
        pod_api_url = params.pod_api_url
        if pod_api_url:
            result = json.loads(unicode(urllib2.urlopen(pod_api_url, data="any").read(), 'utf-8'))
            post_url = result['post_url'].encode('utf-8')
            response = {
                'state': 'ok',
                'redirect_url': result['redirect_url'].encode('utf-8'),
            }
        else:
            try:
                post_url = post_data['post_url']
            except KeyError:
                return self.error_response('POST argument required: post_url')
            response = {'state': 'ok'}
        
        log.info('zip_post %s %s' % (collection_id, pod_api_url))
        params.post_url = post_url
        
        self.qserve.qadd(channel="post", # jobid="%s:post" % collection_id,
                         payload=dict(params=params.__dict__))
        return response

def _parse_qs(qs):
    for i, x in enumerate(qs):
        if ":" in x:
            host, port = x.split(":", 1)
            port = int(port)
            qs[i] = (host, port)
        else:
            qs[i] = (x, 14311)
    
def main():
    from gevent import pywsgi as wsgi
    # from gevent import wsgi

    WSGIServer = wsgi.WSGIServer
    WSGIHandler = wsgi.WSGIHandler

    WSGIHandler.log_request = lambda *args, **kwargs: None

    import argv
    opts,  args = argv.parse(sys.argv[1:], "--qserve= --port=")
    qs = []
    port = 8899
    for o,a in opts:
        if o=="--port":
            port = int(a)
        elif o=="--qserve":
            qs.append(a)

    if not qs:
        qs.append("localhost:14311")

    _parse_qs(qs)
            
    cachedir = "cache"
    cachedir = utils.ensure_dir(cachedir)
    for i in range(0x100, 0x200):
        p = os.path.join(cachedir, hex(i)[3:])
        if not os.path.isdir(p):
            os.mkdir(p)

    def app(*args, **kwargs):
        return Application(cachedir)(*args, **kwargs)
    
    address = "0.0.0.0", port
    server = WSGIServer(address, app)

    for x in qs:
        worker.Worker.spawn(wait_idle, x, busy).set_max_rate((5, 0))
    
    try:
        print "listening on %s:%d" % address
        server.serve_forever()
    except KeyboardInterrupt:
        server.stop()
        print "bye."

if __name__=="__main__":
    main()
