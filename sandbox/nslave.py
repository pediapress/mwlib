#! /usr/bin/env python

import os
import simplejson as json

cachedir = "cache"

def get_collection_dir(collection_id):
    return os.path.join(cachedir, collection_id[:2], collection_id)


class commands(object):
    def statusfile(self):
        host = self.proxy._rpcclient.host
        port = self.proxy._rpcclient.port
        return 'qserve://%s:%s/%s' % (host, port, self.jobid)
        
    def rpc_makezip(self, metabook_data=None, collection_id=None, base_url=None):
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

        if metabook_data:
            f = open(metabook_path, 'wb')
            f.write(metabook_data)
            f.close()

        cmd = " ".join(args)
        print "running:", cmd
        os.system(cmd)

    def rpc_render(self, metabook_data=None, collection_id=None, base_url=None, writer=None):
        writer = writer or "rl"
        dir = get_collection_dir(collection_id)
        def getpath(p):
            return os.path.join(dir, p)

        self.qaddw(channel="makezip", payload=dict(metabook_data=metabook_data, collection_id=collection_id), jobid="%s:makezip" % (collection_id, ))
        args = ["mw-render",  "-w",  writer, "-c", getpath("collection.zip"), "-o", getpath("output.%s" % writer),  "--status", self.statusfile()]
        os.system(" ".join(args))

    def rpc_post(self, metabook_data=None, collection_id=None, base_url=None, post_url=None):
        dir = get_collection_dir(collection_id)
        def getpath(p):
            return os.path.join(dir, p)

        self.qaddw(channel="makezip", payload=dict(metabook_data=metabook_data, collection_id=collection_id), jobid="%s:makezip" % (collection_id, ))
        print locals()
        args = ["mw-post", "-i", getpath("collection.zip"), "-p", post_url]
        os.system(" ".join(args))
        
        
from mwlib.async.slave import main
main(commands,numprocs=2)
