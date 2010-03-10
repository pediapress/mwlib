#! /usr/bin/env python

"""WSGI server interface to mw-render and mw-zip/mw-post"""
import gevent.monkey
gevent.monkey.patch_socket()

import sys
import errno
import os
import re
import shutil
import signal
import StringIO
import time
import urllib2
import urlparse
import traceback

from hashlib import md5

from mwlib import myjson as json

from webob import Request, Response

from mwlib import log, utils, _version
from mwlib.metabook import calc_checksum
from mwlib.status import Status

from mwlib.async import rpcclient

log = log.Log('mwlib.serve')

class bunch(object):
    pass

class colldir(object):
    def __init__(self, path):
        self.dir = os.path.abspath(path)

    def getpath(self, p):
        return os.path.join(self.dir, p)

    
class FileIterable(object):
    def __init__(self, filename):
        self.filename = filename

    def __iter__(self):
        return FileIterator(self.filename)

class FileIterator(object):
    chunk_size = 4096

    def __init__(self, filename):
        self.filename = filename
        self.fileobj = open(self.filename, 'rb')

    def __iter__(self):
        return self

    def next(self):
        chunk = self.fileobj.read(self.chunk_size)
        if not chunk:
            raise StopIteration()
        return chunk



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
        mbobj = json.loads(unicode(mb, 'utf-8'))
        sio.write(calc_checksum(mbobj))
        num_articles = len(list(mbobj.articles()))
        sys.stdout.write("new-collection %s\t%r\t%r\n" % (num_articles, data.get("base_url"), data.get("writer")))
        
    return md5(sio.getvalue()).hexdigest()[:16]

# ==============================================================================

def json_response(fn):
    """Decorator wrapping result of decorated function in JSON response"""
    
    def wrapper(*args, **kwargs):
        result = fn(*args, **kwargs)
        if isinstance(result, Response):
            return result
        return Response(json.dumps(result), content_type='application/json')
    return wrapper

# ==============================================================================

class Application(object):
    metabook_filename = 'metabook.json'
    error_filename = 'errors'
    status_filename = 'status'
    output_filename = 'output'
    pid_filename = 'pid'
    zip_filename = 'collection.zip'
    mwpostlog_filename = 'mw-post.log'
    mwziplog_filename = 'mw-zip.log'
    mwrenderlog_filename = 'mw-render.log'
    
    def __init__(self,
                 cache_dir="cache",
                 default_writer='rl',
                 report_from_mail=None,
                 report_recipients=None):
        
        self.cache_dir = utils.ensure_dir(cache_dir)
        self.mwrender_cmd = "mw-render"
        self.mwrender_logfile = "render-logfile"
        self.mwzip_cmd = "mw-zip"
        self.mwzip_logfile = "zip-logfile"
        self.mwpost_cmd = "mw-post"
        self.mwpost_logfile = "post-logfile"
        
            
        self.default_writer = default_writer
        self.report_from_mail = report_from_mail
        self.report_recipients = report_recipients

        self.qserve = rpcclient.serverproxy()
        
        
        for i in range(0x100, 0x200):
            p = os.path.join(self.cache_dir, hex(i)[3:])
            if not os.path.isdir(p):
                os.mkdir(p)
            
    def __call__(self, environ, start_response):
        request = Request(environ)

        try:
            log.request_info('remote_addr: %s, referer: %s' % (
                request.remote_addr, request.referer
            ))
        except:
            pass

        if request.method != 'POST':
            response = Response(status=405)
        else:
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
        
        if not self.check_collection_id(collection_id):
            return Response(status=404)

        try:
            return method(collection_id, request.params, is_new)
        except Exception, exc:
            traceback.print_exc()
            self.send_report_mail('exception', command=command)
            return self.error_response('error executing command %r: %s' % (
                    command, exc,))
    
    @json_response
    def error_response(self, error):
        if isinstance(error, str):
            error = unicode(error, 'utf-8', 'ignore')
        elif not isinstance(error, unicode):
            error = unicode(repr(error), 'ascii')
        return {'error': error}
    
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
        collection_dir = self.get_collection_dir(collection_id)
        return os.path.exists(collection_dir)
    
    def new_collection(self, post_data):
        collection_id = make_collection_id(post_data)
        colldir = self.get_collection_dir(collection_id)
        
        try:
            log.info('Creating directory %r' % colldir)
            os.mkdir(colldir)
        except OSError, exc:
            if getattr(exc, 'errno') not in (errno.EEXIST, errno.EISDIR):
                raise
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
    


    def _get_params(self, post_data):
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
            language = g('language', ''))
        return params
    
    
    @json_response
    def do_render(self, collection_id, post_data, is_new=False):
        params = self._get_params(post_data)        
        metabook_data = params.metabook_data
        base_url = params.base_url
        writer = params.writer
        force_render = params.force_render
        
        
        
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
        
        self.qserve.qadd(channel="render", payload=dict(collection_id=collection_id, metabook_data=metabook_data),
                         jobid="%s:render-%s" % (collection_id, writer))

        return response
        
        # args = [
        #     self.mwrender_cmd,
        #     '--logfile', logfile,
        #     '--error-file', error_path,
        #     '--status-file', status_path,
        #     '--writer', writer,
        #     '--output', output_path,
        # ]
        

        
        # zip_path = self.get_path(collection_id, self.zip_filename)
        # if not force_render and os.path.exists(zip_path):
        #     log.info('using existing ZIP file to render %r' % output_path)
        #     args.extend(['--config', zip_path])
        #     if writer_options:
        #         args.extend(['--writer-options', writer_options])
        #     if template_blacklist:
        #         args.extend(['--template-blacklist', template_blacklist])
        #     if template_exclusion_category:
        #         args.extend(['--template-exclusion-category', template_exclusion_category])
        #     if print_template_prefix:
        #         args.extend(['--print-template-prefix', print_template_prefix])
        #     if print_template_pattern:
        #         args.extend(['--print-template-pattern', print_template_pattern])
        #     if language:
        #         args.extend(['--language', language])
        # else:
        #     log.info('rendering %r' % output_path)
        #     metabook_path = self.get_path(collection_id, self.metabook_filename)
        #     if metabook_data:
        #         f = open(metabook_path, 'wb')
        #         f.write(metabook_data)
        #         f.close()
        #     args.extend([
        #         '--metabook', metabook_path,
        #         '--keep-zip', zip_path,
        #     ])
        #     if base_url:
        #         args.extend(['--config', base_url])
        #     if writer_options:
        #         args.extend(['--writer-options', writer_options])
        #     if template_blacklist:
        #         args.extend(['--template-blacklist', template_blacklist])
        #     if template_exclusion_category:
        #         args.extend(['--template-exclusion-category', template_exclusion_category])
        #     if print_template_prefix:
        #         args.extend(['--print-template-prefix', print_template_prefix])
        #     if print_template_pattern:
        #         args.extend(['--print-template-pattern', print_template_pattern])
        #     if login_credentials:
        #         login = login_credentials.split(":", 2)
        #         if len(login)==2:
        #             user, password = login
        #             domain=None
        #         elif len(login)==3:
        #             user, password, domain = login
        #         else:
        #             raise RuntimeError("bad login_credentials argument")
        #         args.extend(["--username",  user, "--password", password])
                
        #         if domain:
        #             args.extend(["--domain", domain])
                    
        #     if script_extension:
        #         args.extend(['--script-extension', script_extension])
        #     if language:
        #         args.extend(['--language', language])
        
        # Status(status_path)(status='job queued', progress=0)
        # self.queue_render_job('render', collection_id, args)
        
        # return response
    
    def read_status_file(self, collection_id, writer):
        status_path = self.get_path(collection_id, self.status_filename, writer)
        try:
            f = open(status_path, 'rb')
            return json.loads(unicode(f.read(), 'utf-8'))
            f.close()
        except (IOError, ValueError):
            return {'progress': 0}
    
    @json_response
    def do_render_status(self, collection_id, post_data, is_new=False):
        if is_new:
            return self.error_response('POST argument required: collection_id')

        def retval(**kw):
            return dict(collection_id=collection_id, writer=writer, **kw)
        
        writer = post_data.get('writer', self.default_writer)
            
        log.info('render_status %s %s' % (collection_id, writer))
        
        jobid="%s:render-%s" % (collection_id, writer)
        
        res = self.qserve.qinfo(jobid=jobid)
        info = res.get("info", {})
        done = res.get("done", False)
        error = res.get("error", None)

        if error:    
            return retval(state="failed", error=error)

        if done:
            return retval(state="finished")

        
        if not info:
            jobid="%s:makezip" % (collection_id,)
            res = self.qserve.qinfo(jobid=jobid)
            info = res.get("info", {})
        
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
        
        try:
            log.info('download %s %s' % (collection_id, writer))
        
            output_path = self.get_path(collection_id, self.output_filename, writer)
            os.utime(output_path, None)
            status = self.read_status_file(collection_id, writer)
            response = Response()
            response.app_iter = FileIterable(output_path)
            response.content_length = os.path.getsize(output_path)
            if 'content_type' in status:
                response.content_type = status['content_type'].encode('utf-8', 'ignore')
            else:
                log.warn('no content type in status file')
            if 'file_extension' in status:
                response.headers['Content-Disposition'] = 'inline; filename=collection.%s' %  (
                    status['file_extension'].encode('utf-8', 'ignore'),
                )
            else:
                log.warn('no file extension in status file')
            return response
        except Exception, exc:
            log.ERROR('exception in do_download(): %r' % exc)
            return Response(status=500)
    
    @json_response
    def do_zip_post(self, collection_id, post_data, is_new=False):
        try:
            metabook_data = post_data['metabook']
        except KeyError, exc:
            return self.error_response('POST argument required: %s' % exc)
        
        base_url = post_data.get('base_url')
        template_blacklist = post_data.get('template_blacklist', '')
        template_exclusion_category = post_data.get('template_exclusion_category', '')
        print_template_prefix = post_data.get('print_template_prefix', '')
        print_template_pattern = post_data.get('print_template_pattern', '')
        login_credentials = post_data.get('login_credentials', '')
        script_extension = post_data.get('script_extension', '')
        
        pod_api_url = post_data.get('pod_api_url', '')
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

        self.qserve.qadd(channel="post", jobid="%s:post" % collection_id,
                         payload=dict(collection_id=collection_id, metabook_data=metabook_data, post_url=post_url))
        return response
    

# ==============================================================================

def get_collection_dirs(cache_dir):
    """Generator yielding full paths of collection directories"""

    for dirpath, dirnames, filenames in os.walk(cache_dir):
        for d in dirnames:
            if collection_id_rex.match(d):
                yield os.path.join(dirpath, d)

def purge_cache(max_age, cache_dir):
    """Remove all subdirectories of cache_dir whose mtime is before now-max_age
    
    @param max_age: max age of directories in seconds
    @type max_age: int
    
    @param cache_dir: cache directory
    @type cache_dir: basestring
    """
    
    now = time.time()
    for path in get_collection_dirs(cache_dir):
        for fn in os.listdir(path):
            if now - os.stat(os.path.join(path, fn)).st_mtime > max_age:
                break
        else:
            continue
        try:
            log.info('removing directory %r' % path)
            shutil.rmtree(path)
        except Exception, exc:
            log.ERROR('could not remove directory %r: %s' % (path, exc))
    
def clean_up(cache_dir, max_running_time, report=None):
    """Look for PID files whose processes have not finished/erred but ceased
    to exist => remove cache directories. Look for long running processes =>
    send SIGKILL.
    """

    now = time.time()


    def error(msg):
        log.ERROR(msg)
        if report is not None:
            report(msg)

    for path in get_collection_dirs(cache_dir):
        for e in os.listdir(path):
            if '.' not in e:
                continue
            parts = e.split('.')
            if parts[0] != Application.pid_filename:
                continue
            ext = parts[1]
            if not ext:
                continue
            pid_file = os.path.join(path, e)
            try:
                pid = int(open(pid_file, 'rb').read())
            except ValueError:
                error('pid file %r with invalid contents' % pid_file)
                continue
            except IOError, exc:
                error('Could not read PID file %r: %s' % (pid_file, exc))
                continue

            error_file = os.path.join(path, '%s.%s' % (Application.error_filename, ext))
            
            try:
                os.kill(pid, 0)
            except OSError, exc:
                if exc.errno == 3: # No such process
                    sys.exc_clear()
                    error('Have dangling pid file %r' % pid_file)
                    os.unlink(pid_file)
                    if not os.path.exists(error_file):
                        open(error_file, 'wb').write('Process died.\n')
                    continue

            try:
                st = os.stat(pid_file)
            except Exception, exc:
                error('Could not stat pid file %r: %s' % (pid_file, exc))
                continue
            if now - st.st_mtime < max_running_time:
                continue

            error('Have long running process with pid %d (%s s, pid file %r)' % (pid, now - st.st_mtime, pid_file))
            try:
                log.info('sending SIGKILL to pid %d' % pid)
                os.kill(pid, signal.SIGKILL)
                if not os.path.exists(error_file):
                    open(error_file, 'wb').write('Long running process killed.\n')
            except Exception, exc:
                error('Could not send SIGKILL: %s' % exc)


from gevent.wsgi import WSGIServer,  WSGIHandler

class handler(WSGIHandler):
    def alog_request(self, *args, **kwargs):
        pass

def main():
    application = Application()
    
    address = "localhost", 8899
    server = WSGIServer(address, application,  handler_class=handler)
    
    try:
        print "listening on %s:%d" % address
        server.serve_forever()
    except KeyboardInterrupt:
        server.stop()
        print "Bye bye"

if __name__=="__main__":
    main()
