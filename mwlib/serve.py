#! /usr/bin/env python

"""WSGI server interface to mw-render and mw-zip/mw-post"""

import sys
import errno
import os
import re
import shutil
import signal
import StringIO
import subprocess
import time
import urllib2
import urlparse

from hashlib import md5

from mwlib import myjson as json

from webob import Request, Response

from mwlib import filequeue, log, utils, _version
from mwlib.metabook import calc_checksum
from mwlib.status import Status

# ==============================================================================

log = log.Log('mwlib.serve')

# ==============================================================================


def FileLock(path, threaded=True):
    """lazy wrapper around lockfile.Lockfile.
    
    importing the lockfile module creates a temporary file for the
    SQLiteFileLock class. This fails when when the disk is full and
    will stop mw-serve-ctl from running
    """
    
    import lockfile
    return lockfile.FileLock(path, threaded=threaded)


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


# ==============================================================================

def no_job_queue(job_type, collection_id, args):
    """Just spawn a new process for the given job"""
    
    if os.name == 'nt':
        kwargs = {}
    else:
        kwargs = {'close_fds': True}
    try:
        log.info('queuing %r' % args)
        subprocess.Popen(args, **kwargs)
    except OSError, exc:
        raise RuntimeError('Could not execute command %r: %s' % (
            args[0], exc,
        ))


# ==============================================================================

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
    
    def __init__(self, cache_dir,
        mwrender_cmd, mwrender_logfile,
        mwzip_cmd, mwzip_logfile,
        mwpost_cmd, mwpost_logfile,
        queue_dir,
        default_writer='rl',
        report_from_mail=None,
        report_recipients=None,
    ):
        self.cache_dir = utils.ensure_dir(cache_dir)
        self.mwrender_cmd = mwrender_cmd
        self.mwrender_logfile = mwrender_logfile
        self.mwzip_cmd = mwzip_cmd
        self.mwzip_logfile = mwzip_logfile
        self.mwpost_cmd = mwpost_cmd
        self.mwpost_logfile = mwpost_logfile
        self.queue_upload_job = self.queue_render_job = no_job_queue
        if queue_dir:
            self.queue_render_job = filequeue.FileJobQueuer(utils.ensure_dir(queue_dir))
        self.default_writer = default_writer
        self.report_from_mail = report_from_mail
        self.report_recipients = report_recipients

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

        lock = FileLock(self.get_collection_dir(collection_id))
        lock.acquire()
        try:
            return method(collection_id, request.params, is_new)
        except Exception, exc:
            self.send_report_mail('exception', command=command)
            return self.error_response('error executing command %r: %s' % (
                    command, exc,))
        finally:
            lock.release()
    
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
    
                     
    @json_response
    def do_render(self, collection_id, post_data, is_new=False):
        metabook_data = post_data.get('metabook')
        if is_new and not metabook_data:
            return self.error_response('POST argument metabook or collection_id required')
        if not is_new and metabook_data:
            return self.error_response('Specify either metabook or collection_id, not both')
        try:
            writer = post_data.get('writer', self.default_writer)
        except KeyError, exc:
            return self.error_response('POST argument required: %s' % exc)
        
        base_url = post_data.get('base_url')
        
        if base_url and not self.is_good_baseurl(base_url):
            log.bad("bad base_url: %r" % (base_url, ))
            return self.error_response("bad base_url %r. check your $wgServer and $wgScriptPath variables" % (base_url, ))
        
        writer_options = post_data.get('writer_options', '')
        template_blacklist = post_data.get('template_blacklist', '')
        template_exclusion_category = post_data.get('template_exclusion_category', '')
        print_template_prefix = post_data.get('print_template_prefix', '')
        print_template_pattern = post_data.get('print_template_pattern', '')
        login_credentials = post_data.get('login_credentials', '')
        force_render = bool(post_data.get('force_render'))
        script_extension = post_data.get('script_extension', '')
        language = post_data.get('language', '')
        
        log.info('render %s %s' % (collection_id, writer))
        
        response = {
            'collection_id': collection_id,
            'writer': writer,
            'is_cached': False,
        }
        
        pid_path = self.get_path(collection_id, self.pid_filename, writer)
        if os.path.exists(pid_path):
            log.info('mw-render already running for collection %r' % collection_id)
            return response
        
        output_path = self.get_path(collection_id, self.output_filename, writer)
        if os.path.exists(output_path):
            if force_render:
                log.info('removing rendered file %r (forced rendering)' % output_path)
                utils.safe_unlink(output_path)
            else:
                log.info('re-using rendered file %r' % output_path)
                response['is_cached'] = True
                return response
        
        error_path = self.get_path(collection_id, self.error_filename, writer)
        if os.path.exists(error_path):
            log.info('removing error file %r' % error_path)
            utils.safe_unlink(error_path)
            mail_sent = self.get_path(collection_id, "mail-sent")
            if os.path.exists(mail_sent):
                utils.safe_unlink(mail_sent)
                
            force_render = True
        
        status_path = self.get_path(collection_id, self.status_filename, writer)
        if os.path.exists(status_path):
            if force_render:
                log.info('removing status file %r (forced rendering)' % status_path)
                utils.safe_unlink(status_path)
            else:
                log.info('status file exists %r' % status_path)
                return response
        
        if self.mwrender_logfile:
            logfile = self.mwrender_logfile
        else:
            logfile = self.get_path(collection_id, self.mwrenderlog_filename, writer)
        
        args = [
            self.mwrender_cmd,
            '--logfile', logfile,
            '--error-file', error_path,
            '--status-file', status_path,
            '--writer', writer,
            '--output', output_path,
            '--pid-file', pid_path,
        ]
        
        zip_path = self.get_path(collection_id, self.zip_filename)
        if not force_render and os.path.exists(zip_path):
            log.info('using existing ZIP file to render %r' % output_path)
            args.extend(['--config', zip_path])
            if writer_options:
                args.extend(['--writer-options', writer_options])
            if template_blacklist:
                args.extend(['--template-blacklist', template_blacklist])
            if template_exclusion_category:
                args.extend(['--template-exclusion-category', template_exclusion_category])
            if print_template_prefix:
                args.extend(['--print-template-prefix', print_template_prefix])
            if print_template_pattern:
                args.extend(['--print-template-pattern', print_template_pattern])
            if language:
                args.extend(['--language', language])
        else:
            log.info('rendering %r' % output_path)
            metabook_path = self.get_path(collection_id, self.metabook_filename)
            if metabook_data:
                f = open(metabook_path, 'wb')
                f.write(metabook_data)
                f.close()
            args.extend([
                '--metabook', metabook_path,
                '--keep-zip', zip_path,
            ])
            if base_url:
                args.extend(['--config', base_url])
            if writer_options:
                args.extend(['--writer-options', writer_options])
            if template_blacklist:
                args.extend(['--template-blacklist', template_blacklist])
            if template_exclusion_category:
                args.extend(['--template-exclusion-category', template_exclusion_category])
            if print_template_prefix:
                args.extend(['--print-template-prefix', print_template_prefix])
            if print_template_pattern:
                args.extend(['--print-template-pattern', print_template_pattern])
            if login_credentials:
                login = login_credentials.split(":", 2)
                if len(login)==2:
                    user, password = login
                    domain=None
                elif len(login)==3:
                    user, password, domain = login
                else:
                    raise RuntimeError("bad login_credentials argument")
                args.extend(["--username",  user, "--password", password])
                
                if domain:
                    args.extend(["--domain", domain])
                    
            if script_extension:
                args.extend(['--script-extension', script_extension])
            if language:
                args.extend(['--language', language])
        
        Status(status_path)(status='job queued', progress=0)
        self.queue_render_job('render', collection_id, args)
        
        return response
    
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
        
        output_path = self.get_path(collection_id, self.output_filename, writer)
        if os.path.exists(output_path):
            return retval(state="finished")
        
        error_path = self.get_path(collection_id, self.error_filename, writer)
        if os.path.exists(error_path):
            text = unicode(open(error_path, 'rb').read(), 'utf-8', 'ignore')
            if text.startswith('traceback\n'):
                metabook_path = self.get_path(collection_id, self.metabook_filename)
                if os.path.exists(metabook_path):
                    metabook = unicode(open(metabook_path, 'rb').read(), 'utf-8', 'ignore')
                else:
                    metabook = None
                mail_sent = self.get_path(collection_id, "mail-sent")
                if not os.path.exists(mail_sent):
                    self.send_report_mail('rendering failed',
                        collection_id=collection_id,
                        writer=writer,
                        error=text,
                        metabook=metabook,
                    )
                    open(mail_sent, "w")
            return retval(state="failed", error=text)

        status = self.read_status_file(collection_id, writer)
        if status.get('state') == 'error':
            return retval(state="failed", error="unknown error")
        
        return retval(state="progress", status=status)
    
    @json_response
    def do_render_kill(self, collection_id, post_data, is_new=False):
        if is_new:
            return self.error_response('POST argument required: collection_id')

        writer = post_data.get('writer', self.default_writer)
        
        log.info('render_kill %s %s' % (collection_id, writer))
        
        pid_path = self.get_path(collection_id, self.pid_filename, writer)
        killed = False
        try:
            pid = int(open(pid_path, 'rb').read())
            os.kill(pid, signal.SIGKILL)
            killed = True
        except (OSError, ValueError, IOError):
            pass
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
        
        pid_path = self.get_path(collection_id, self.pid_filename, 'zip')
        zip_path = self.get_path(collection_id, self.zip_filename)
        if os.path.exists(zip_path):
            log.info('POSTing ZIP file %r' % zip_path)
            if self.mwpost_logfile:
                logfile = self.mwpost_logfile
            else:
                logfile = self.get_path(collection_id, self.mwpostlog_filename)
            args = [
                self.mwpost_cmd,
                '--logfile', logfile,
                '--posturl', post_url,
                '--input', zip_path,
                '--pid-file', pid_path,
            ]
        else:
            log.info('Creating and POSting ZIP file %r' % zip_path)
            if self.mwzip_logfile:
                logfile = self.mwzip_logfile
            else:
                logfile = self.get_path(collection_id, self.mwziplog_filename)
            metabook_path = self.get_path(collection_id, self.metabook_filename)
            f = open(metabook_path, 'wb')
            f.write(metabook_data)
            f.close()
            args = [
                self.mwzip_cmd,
                '--logfile', logfile,
                '--metabook', metabook_path,
                '--posturl', post_url,
                '--output', zip_path,
                '--pid-file', pid_path,
            ]
            if base_url:
                args.extend(['--config', base_url])
            if template_blacklist:
                args.extend(['--template-blacklist', template_blacklist])
            if template_exclusion_category:
                args.extend(['--template-exclusion-category', template_exclusion_category])
            if print_template_prefix:
                args.extend(['--print-template-prefix', print_template_prefix])
            if print_template_pattern:
                args.extend(['--print-template-pattern', print_template_pattern])
            if login_credentials:
                args.extend(['--login', login_credentials])
            if script_extension:
                args.extend(['--script-extension', script_extension])
        
        self.queue_upload_job('post', collection_id, args)
        
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






