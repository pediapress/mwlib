#! /usr/bin/env python

import os, subprocess
import simplejson as json

cachedir = "cache"

def get_collection_dir(collection_id):
    return os.path.join(cachedir, collection_id[:2], collection_id)

def system(args):
    print "running %r" % (" ".join(args))
    retcode = subprocess.call(args)
    if retcode != 0:
        raise RuntimeError("command failed: %r" % args)

def _get_args(writer_options=None,
              template_blacklist=None,
              template_exclusion_category=None,
              print_template_prefix=None,
              print_template_pattern=None,
              language=None,
              **kw):
    
    args = []
    
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

    return args

class commands(object):
    def statusfile(self):
        host = self.proxy._rpcclient.host
        port = self.proxy._rpcclient.port
        return 'qserve://%s:%s/%s' % (host, port, self.jobid)
        
    def rpc_makezip(self, params=None):
        def doit(metabook_data=None, collection_id=None, base_url=None,  **kw):
            print "rpc_makezip:",  metabook_data
            mb = json.loads(metabook_data)
            print "metabook:", mb

            dir = get_collection_dir(collection_id)
            def getpath(p):
                return os.path.join(dir, p)

            zip_path = getpath("collection.zip")
            if os.path.exists(zip_path):
                return

            metabook_path = getpath("metabook.json")

            args = ["mw-zip", "-o", zip_path, "-m", metabook_path, "--status", self.statusfile()]
            if base_url:
                args.extend(['--config', base_url])
                
            args.extend(_get_args(**params))

            if metabook_data:
                f = open(metabook_path, 'wb')
                f.write(metabook_data)
                f.close()

            system(args)

        return doit(**params)
    
    def rpc_render(self, params=None):
        def doit(metabook_data=None, collection_id=None, base_url=None, writer=None, **kw):
            print "\n=========="
            print locals()
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
              
        
from mwlib.async.slave import main
main(commands,numprocs=2)
