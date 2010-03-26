#! /usr/bin/env python

import os, sys, time, subprocess

cachedir = "cache"

def get_collection_dir(collection_id):
    return os.path.join(cachedir, collection_id[:2], collection_id)

def system(args):
    stime=time.time()
    devnull = open("/dev/null", "r")
    p = subprocess.Popen(args, stdin=devnull, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = p.communicate()
    retcode = p.wait()

    d = time.time()-stime

    msg = []
    a = msg.append
    a("%s %s %r\n" % (retcode, d, args))
        
    writemsg = lambda: sys.stderr.write("".join(msg))
    
    if retcode != 0:
        a(stdout)
        a("\n====================\n")
        a(stderr)
        
        writemsg()
        raise RuntimeError("command failed: %r" % args)

    writemsg()
    

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

            system(args)

        return doit(**params)
    
    def rpc_render(self, params=None):
        def doit(metabook_data=None, collection_id=None, base_url=None, writer=None, **kw):
            writer = writer or "rl"
            dir = get_collection_dir(collection_id)
            def getpath(p):
                return os.path.join(dir, p)

            self.qaddw(channel="makezip", payload=dict(params=params), jobid="%s:makezip" % (collection_id, ))
            args = ["mw-render",  "-w",  writer, "-c", getpath("collection.zip"), "-o", getpath("output.%s" % writer),  "--status", self.statusfile()]

            args.extend(_get_args(**params))
            
            system(args)
            
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
    global cachedir
    import argv
    opts, args = argv.parse(sys.argv[1:], "--cachedir=")
    for o, a in opts:
        if o=="--cachedir":
            cachedir = a
            
        
    from mwlib.async import slave
    slave.main(commands, numprocs=16, argv=args)
    
if __name__=="__main__":        
    main()
