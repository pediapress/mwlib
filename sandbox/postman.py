#! /usr/bin/env python

import gevent, gevent.monkey
gevent.monkey.patch_all()

import os, sys, getpass, socket, traceback, StringIO

from mwlib.podclient import PODClient
from mwlib.status import Status
from mwlib.utils import send_mail

cachedir = "cache"

def get_collection_dir(collection_id):
    return os.path.join(cachedir, collection_id[:2], collection_id)

    

def _get_args(writer_options=None,
              template_blacklist=None,
              template_exclusion_category=None,
              print_template_prefix=None,
              print_template_pattern=None,
              language=None,
              zip_only=False, 
              **kw):
    
    args = []
    
        
    if template_blacklist:
        args.extend(['--template-blacklist', template_blacklist])
    if template_exclusion_category:
        args.extend(['--template-exclusion-category', template_exclusion_category])
    if print_template_prefix:
        args.extend(['--print-template-prefix', print_template_prefix])
    if print_template_pattern:
        args.extend(['--print-template-pattern', print_template_pattern])

    if zip_only:
        return args
    
    if writer_options:
        args.extend(['--writer-options', writer_options])

    if language:
        args.extend(['--language', language])

    return args

def uploadfile(ipath, posturl, fh=None):
    if fh is None:
        fh = open(ipath, "rb")
    
    podclient = PODClient(posturl)

    status = Status(podclient=podclient)
    
    try:
        status(status='uploading', progress=0)
        podclient.streaming_post_zipfile(ipath, fh)
        status(status='finished', progress=100)
    except Exception, err:
        status(status='error')
        raise err


    
def report_upload_status(posturl, fh):
    podclient = PODClient(posturl)
    
    fh.seek(0, 2)
    size = fh.tell()
    fh.seek(0, 0)

    status = Status(podclient=podclient)
    numdots = 0
    
    last = None
    while 1:
        cur = fh.tell()
        if cur != last:
            if cur==size:
                break
            numdots = (numdots + 1) % 10
            status("uploading"+"."*numdots,  progress=100.0*cur/size)
            last = cur
                
        else:
            gevent.sleep(0.1)

def report_mwzip_status(posturl, jobid, host, port):
    podclient = PODClient(posturl)
    status = Status(podclient=podclient)
    
    from mwlib.async import rpcclient
    sp = rpcclient.serverproxy(host, port)

    last = {}
    while 1:
        res = sp.qinfo(jobid=jobid) or {}
        
        done = res.get("done", False)
        if done:
            break
        info = res.get("info", {})
        if info!=last:
            status(status=info.get("status", "fetching"),
                   progress=info.get("progress", 0.0))
            last = info
        else:
            gevent.sleep(0.5)
        
def report_exception(posturl, (tp, err, tb)):
    print "reporting error to", posturl, repr(str(err)[:50])

    podclient = PODClient(posturl)
    podclient.post_status(error=str(err))

mailfrom = "%s@%s" % (getpass.getuser(), socket.gethostname())

def report_exception_mail(subject, exc_info):
    mailto = os.environ.get("MAILTO")
    if not mailto:
        print "MAILTO not set. not sending email."
        return

    print "sending mail to", mailto

    f=StringIO.StringIO()
    traceback.print_exception(*exc_info, file=f)

    send_mail(mailfrom, [mailto], subject, f.getvalue())


class commands(object):
    def statusfile(self):
        host = self.proxy._rpcclient.host
        port = self.proxy._rpcclient.port
        return 'qserve://%s:%s/%s' % (host, port, self.jobid)
    
    def rpc_post(self, params):
        post_url = params["post_url"]

        def _doit(metabook_data=None, collection_id=None, base_url=None, post_url=None, **kw):
            dir = get_collection_dir(collection_id)
            def getpath(p):
                return os.path.join(dir, p)

            jobid = "%s:makezip" % (collection_id, )
            g=gevent.spawn_later(0.2, report_mwzip_status, post_url, jobid, self.proxy._rpcclient.host, self.proxy._rpcclient.port)

            try:
                self.qaddw(channel="makezip", payload=dict(params=params), jobid=jobid)
            finally:
                g.kill()
                del g
                
            ipath = getpath("collection.zip")
            fh = open(ipath, "rb")
            
            g=gevent.spawn(report_upload_status, post_url, fh)
            try:
                uploadfile(ipath, post_url, fh)
            finally:
                g.kill()
                del g

        def doit(**params):
            try:
                return _doit(**params)
            except Exception:
                exc_info = sys.exc_info()
                gevent.spawn(report_exception, post_url, exc_info)
                gevent.spawn(report_exception_mail, "zip upload failed", exc_info)
                del exc_info
                raise

        return doit(**params)

def main():
    global cachedir
    import argv
    opts, args = argv.parse(sys.argv[1:], "--cachedir=")
    for o, a in opts:
        if o=="--cachedir":
            cachedir = a
        
    from mwlib.async import slave
    
    slave.main(commands, numgreenlets=32, argv=args)
    
if __name__=="__main__":        
    main()
