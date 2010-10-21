#! /usr/bin/env python

from gevent import monkey
monkey.patch_all()

import os, sys, time

cachedir = "cache"
cacheurl = None

from mwlib.async import proc
from mwlib.utils import garble_password

def get_collection_dir(collection_id):
    return os.path.join(cachedir, collection_id[:2], collection_id)

def system(args, timeout=None):
    stime=time.time()

    retcode, stdout = proc.run_cmd(args, timeout=timeout)

    d = time.time()-stime

    pub_args = garble_password(args)
    msg = []
    a = msg.append
    a("%s %s %r\n" % (retcode, d, pub_args))
        
    writemsg = lambda: sys.stderr.write("".join(msg))
    
    if retcode != 0:
        a(stdout)
        a("\n====================\n")

        writemsg()
        lines = ["    " + x for x in stdout[-4096:].split("\n")]
        raise RuntimeError("command failed with returncode %s: %r\nLast Output:\n%s" % (retcode, pub_args,  "\n".join(lines)))

    writemsg()
    

def _get_args(writer_options=None,
              template_blacklist=None,
              template_exclusion_category=None,
              print_template_prefix=None,
              print_template_pattern=None,
              language=None,
              zip_only=False,
              login_credentials=None,
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

    if login_credentials:
        username, password, domain = (login_credentials.split(":", 3)+[None]*3)[:3]
        assert username and password, "bad login_credentials"
        args.extend(["--username", username, "--password", password])
        if domain:
            args.extend(["--domain", domain])

    if zip_only:
        return args
    
    if writer_options:
        args.extend(['--writer-options', writer_options])

    if language:
        args.extend(['--language', language])

    return args

class commands(object):
    def statusfile(self):
        host = self.proxy._rpcclient.host
        port = self.proxy._rpcclient.port
        return 'qserve://%s:%s/%s' % (host, port, self.jobid)
        
    def rpc_makezip(self, params=None):
        def doit(metabook_data=None, collection_id=None, base_url=None,  **kw):
            dir = get_collection_dir(collection_id)
            def getpath(p):
                return os.path.join(dir, p)

            zip_path = getpath("collection.zip")
            if os.path.isdir(dir):
                if os.path.exists(zip_path):
                    return
            else:
                os.mkdir(dir)
                
            metabook_path = getpath("metabook.json")

            args = ["mw-zip", "-o", zip_path, "-m", metabook_path, "--status", self.statusfile()]
            if base_url:
                args.extend(['--config', base_url])
                
            args.extend(_get_args(zip_only=True, **params))

            if metabook_data:
                f = open(metabook_path, 'wb')
                f.write(metabook_data)
                f.close()

            system(args, timeout=8*60.0)

        return doit(**params)
    
    def rpc_render(self, params=None):
        def doit(metabook_data=None, collection_id=None, base_url=None, writer=None, **kw):
            writer = writer or "rl"
            dir = get_collection_dir(collection_id)
            def getpath(p):
                return os.path.join(dir, p)

            self.qaddw(channel="makezip", payload=dict(params=params), jobid="%s:makezip" % (collection_id, ))
            outfile = getpath("output.%s" % writer)
            args = ["mw-render",  "-w",  writer, "-c", getpath("collection.zip"), "-o", outfile,  "--status", self.statusfile()]

            args.extend(_get_args(**params))
            
            system(args, timeout=15*60.0)
            os.chmod(outfile, 0644)
            size = os.path.getsize(outfile)            
            url = cacheurl+"/%s/%s/output.%s" % (collection_id[:2], collection_id, writer)
            return dict(url=url, size=size)
        
        
        
            
        return doit(**params)
    
               
    def rpc_post(self, params):
        def doit(metabook_data=None, collection_id=None, base_url=None, post_url=None, **kw):
            dir = get_collection_dir(collection_id)
            def getpath(p):
                return os.path.join(dir, p)

            self.qaddw(channel="makezip", payload=dict(params=params), jobid="%s:makezip" % (collection_id, ))
            args = ["mw-post", "-i", getpath("collection.zip"), "-p", post_url]
            system(args)
        return doit(**params)

def main():
    global cachedir, cacheurl
    numgreenlets = 10
    import argv
    opts, args = argv.parse(sys.argv[1:], "--cachedir= --url= --numprocs=")
    for o, a in opts:
        if o=="--cachedir":
            cachedir = a
        if o=="--url":
            cacheurl = a
        if o=="--numprocs":
            numgreenlets = int(a)

    if not cacheurl:
        sys.exit("--url option missing")
        
        
        
    from mwlib.async import slave
    slave.main(commands, numgreenlets=numgreenlets, argv=args)
    
if __name__=="__main__":        
    main()
