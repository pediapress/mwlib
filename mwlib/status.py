
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

import os
import sys
try:
    import simplejson as json
except ImportError:
    import json

from mwlib.log import Log

log = Log('mwlib.status')

class Status(object):
    qproxy = None
    stdout = sys.stdout
    
    def __init__(self,
        filename=None,
        podclient=None,
        progress_range=(0, 100),
        status=None,         
    ):
        self.filename = filename
        self.podclient = podclient
        if status is not None:
            self.status = status
        else:
            self.status = {}
        self.progress_range = progress_range

    
    def getSubRange(self, start, end):
        progress_range = (self.scaleProgress(start), self.scaleProgress(end))
        return Status(filename=self.filename, podclient=self.podclient, status=self.status, progress_range=progress_range)
    
    def scaleProgress(self, progress):
        return (
            self.progress_range[0]
            + progress*(self.progress_range[1] - self.progress_range[0])/100
            )


    def __call__(self, status=None, progress=None, article=None, auto_dump=True,
        **kwargs):
        if status is not None and status != self.status.get('status'):
            self.status['status'] = status
        
        if progress is not None:
            progress = min(max(0, progress), 100)
            progress = self.scaleProgress(progress)
            if progress > self.status.get('progress', -1):
                self.status['progress'] = progress
        
        if article is not None and article != self.status.get('article'):
            if 'article' in self.status and not article: # allow explicitly deleting the article from the status
                del self.status['article']
            else:
                self.status['article'] = article
            


        if self.podclient is not None:
            self.podclient.post_status(**self.status)

        msg = []
        msg.append("%s%%" % (self.status.get("progress", self.progress_range[0]),))
        msg.append(self.status.get("status", ""))
        msg.append(self.status.get("article", ""))
        msg = u" ".join(msg).encode("utf-8")

        if self.stdout:
            isatty = getattr(self.stdout, "isatty", None)
            if isatty and isatty():
                self.stdout.write("\x1b[K"+msg+"\r")
            else:
                self.stdout.write(msg)
            self.stdout.flush()
        
        self.status.update(kwargs)
        
        if auto_dump:
            self.dump()
    
    def dump(self):
        if not self.filename:
            return

        if not self.qproxy and self.filename.startswith("qserve://"):
            fn = self.filename[len("qserve://"):]
            host, jobid=fn.split("/")
            try:
                jobid = int(jobid)
            except ValueError:
                jobid = jobid.strip('"')
                
            if ":" in host:
                host, port = host.split(":")
                port = int(port)
            else:
                port = 14311

            from mwlib.async import rpcclient
            self.qproxy = rpcclient.serverproxy(host=host, port=port)
            self.jobid = jobid

        if self.qproxy:
            self.qproxy.qsetinfo(jobid=self.jobid, info=self.status)
            return
            
        try:    
            open(self.filename + '.tmp', 'wb').write(
                json.dumps(self.status).encode('utf-8')
            )
            os.rename(self.filename + '.tmp', self.filename)
        except Exception, exc:
            log.ERROR('Could not write status file %r: %s' % (
                self.filename, exc
            ))
    
