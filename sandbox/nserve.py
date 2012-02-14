#! /usr/bin/env python

"""WSGI server interface to mw-render and mw-zip/mw-post"""

from __future__ import with_statement

import gevent.monkey
if __name__ == "__main__":
    gevent.monkey.patch_all()

import sys, re, StringIO, urllib2, urlparse, traceback
from hashlib import md5

from gevent import pool, pywsgi

from qs.misc import call_in_loop
from mwlib import myjson as json, log, _version
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

name2writer = {'odf': bunch(file_extension='odt', name='odf', content_type='application/vnd.oasis.opendocument.text'),
               'rl': bunch(file_extension='pdf', name='rl', content_type='application/pdf'),
               'xhtml': bunch(file_extension='html', name='xhtml', content_type='text/xml'),
               'xl': bunch(file_extension='pdf', name='xl', content_type='application/pdf'),
               'zim': bunch(file_extension='zim', name='zim', content_type='application/zim')}


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

collection_id_rex = re.compile(r'^[a-f0-9]{16}$')


def make_collection_id(data):
    sio = StringIO.StringIO()
    sio.write(str(_version.version))
    for key in (
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

from mwlib import lrucache
busy = dict()
collid2qserve = lrucache.lrucache(4000)


class watch_qserve(object):
    getstats_timeout = 3.0
    sleeptime = 2.0

    def __init__(self, (host, port), busy):
        self.host = host
        self.port = port
        self.busy = busy
        self.ident = (host, port)
        self.prefix = "watch: %s:%s:" % (host, port)
        self.qserve = None

    def log(self, msg):
        print self.prefix, msg

    def _serverproxy(self):
        return rpcclient.serverproxy(host=self.host, port=self.port)

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
        except BaseException:
            self.qserve = None
            raise

    def _iterate(self):
        try:
            stats = self._getstats()
            numrender = stats.get("busy",  {}).get("render", 0)
            if numrender > 10:
                self._mark_busy("system overloaded")
            else:
                self._mark_busy(False)
        except gevent.GreenletExit:
            raise
        except Exception, err:
            self._mark_busy("system down")
            self.log("error in watch_qserve: %s" % (err,))

    def __call__(self):
        self.busy[self.ident] = True
        while 1:
            try:
                self._iterate()
            except gevent.GreenletExit:
                raise
            self._sleep()


def choose_idle_qserve():
    import random
    idle = [k for k, v in busy.items() if not v]
    if not idle:
        return None
    return random.choice(idle)  # XXX probably store number of render jobs in busy


from bottle import request, default_app, post, get, HTTPResponse


@get('<path:re:.*>')
@post('<path:re:.*>')
def dispatch_command(path):
    return Application().dispatch(request)


class Application(object):
    def __init__(self, default_writer='rl'):
        self.default_writer = default_writer

    def dispatch(self, request):
        try:
            command = request.params['command']
        except KeyError:
            log.error("no command given")
            raise HTTPResponse("no command given", status=400)

        try:
            method = getattr(self, 'do_%s' % command)
        except AttributeError:
            log.error("no such command: %r" % (command, ))
            raise HTTPResponse("no such command: %r" % (command, ), status=400)

        collection_id = request.params.get('collection_id')
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
                return self.error_response("system overloaded. please try again later.", queue_full=1)
            collid2qserve[collection_id] = qserve

        self.qserve = rpcclient.serverproxy(host=qserve[0], port=qserve[1])

        try:
            return method(collection_id, request.params, is_new)
        except Exception, exc:
            print "ERROR while dispatching %r: %s" % (command, dict(collection_id=collection_id, is_new=is_new, qserve=qserve))
            traceback.print_exc()
            if command == "download":
                raise exc

            return self.error_response('error executing command %r: %s' % (
                    command, exc,))

    def error_response(self, error, **kw):
        if isinstance(error, str):
            error = unicode(error, 'utf-8', 'ignore')
        elif not isinstance(error, unicode):
            error = unicode(repr(error), 'ascii')
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
        netloc = urlparse.urlparse(url)[1].lower()
        if netloc.startswith("localhost") or netloc.startswith("127.0") or netloc.startswith("192.168"):
            return False
        return True

    def _get_params(self, post_data,  collection_id):
        g = post_data.get
        params = bunch()
        params.__dict__ = dict(
            metabook_data=g('metabook'),
            writer=g('writer', self.default_writer),
            base_url=g('base_url'),
            writer_options=g('writer_options', ''),
            template_blacklist=g('template_blacklist', ''),
            template_exclusion_category=g('template_exclusion_category', ''),
            print_template_prefix=g('print_template_prefix', ''),
            print_template_pattern=g('print_template_pattern', ''),
            login_credentials=g('login_credentials', ''),
            force_render=bool(g('force_render')),
            script_extension=g('script_extension', ''),
            pod_api_url=post_data.get('pod_api_url', ''),
            language=g('language', ''))

        params.collection_id = collection_id

        return params

    def do_render(self, collection_id, post_data, is_new=False):
        params = self._get_params(post_data,  collection_id=collection_id)
        metabook_data = params.metabook_data
        base_url = params.base_url
        writer = params.writer

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

        self.qserve.qadd(channel="makezip", payload=dict(params=params.__dict__), jobid="%s:makezip" % (collection_id, ), timeout=20 * 60)

        self.qserve.qadd(channel="render", payload=dict(params=params.__dict__),
                         jobid="%s:render-%s" % (collection_id, writer),  timeout=20 * 60)

        return response

    def do_render_status(self, collection_id, post_data, is_new=False):
        if is_new:
            return self.error_response('POST argument required: collection_id')

        def retval(**kw):
            return dict(collection_id=collection_id, writer=writer, **kw)

        writer = post_data.get('writer', self.default_writer)
        w = name2writer[writer]

        jobid = "%s:render-%s" % (collection_id, writer)

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
            jobid = "%s:makezip" % (collection_id,)
            res = self.qserve.qinfo(jobid=jobid) or {}

            done = res.get("done", False)
            if not done:
                info = res.get("info", {})
            else:
                info = dict(status="data fetched. waiting for render process..")

        return retval(state="progress", status=info)

    def do_download(self, collection_id, post_data, is_new=False):
        if is_new:
            return self.error_response('POST argument required: collection_id')

        writer = post_data.get('writer', self.default_writer)
        w = name2writer[writer]

        jobid = "%s:render-%s" % (collection_id, writer)
        res = self.qserve.qinfo(jobid=jobid) or {}
        download_url = res["result"]["url"]

        print "fetching", download_url
        f = urllib2.urlopen(download_url)
        info = f.info()

        header = {}

        for h in ("Content-Length",):
            v = info.getheader(h)
            if v:
                print "copy header:", h, v
                header[h] = v

        if w.content_type:
            header["Content-Type"] = w.content_type

        if w.file_extension:
            header['Content-Disposition'] = 'inline; filename=collection.%s' % (w.file_extension.encode('utf-8', 'ignore'))

        def readdata():
            while 1:
                d = f.read(4096)
                if not d:
                    break
                yield d

        return HTTPResponse(output=readdata(), header=header)

    def do_zip_post(self, collection_id, post_data, is_new=False):
        params = self._get_params(post_data, collection_id=collection_id)

        try:
            post_data['metabook']
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

        self.qserve.qadd(channel="post",  # jobid="%s:post" % collection_id,
                         payload=dict(params=params.__dict__),
                         timeout=20 * 60)
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
    # pywsgi.WSGIHandler.log_request = lambda *args, **kwargs: None

    from mwlib import argv
    opts,  args = argv.parse(sys.argv[1:], "--qserve= --port= -i= --interface=")
    qs = []
    port = 8899
    interface = "0.0.0.0"
    for o, a in opts:
        if o == "--port":
            port = int(a)
        elif o == "--qserve":
            qs.append(a)
        elif o in ("-i", "--interface"):
            interface = a


    qs += args

    if not qs:
        qs.append("localhost:14311")

    _parse_qs(qs)

    address = interface, port
    server = pywsgi.WSGIServer(address, default_app())

    watchers = pool.Pool()
    for x in qs:
        watchers.spawn(call_in_loop(5.0, watch_qserve(x, busy)))

    try:
        print "listening on %s:%d" % address
        server.serve_forever()
    except KeyboardInterrupt:
        server.stop()
        print "bye."

if __name__ == "__main__":
    main()
