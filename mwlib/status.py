import os
import sys
try:
    import json
except ImportError:
    import simplejson as json

from mwlib.log import Log

log = Log('mwlib.status')

class Status(object):
    def __init__(self,
        filename=None,
        podclient=None,
        progress_range=(0, 100),
        status=None,         
    ):
        self.filename = filename
        self.podclient = podclient
        self.status = status or {}
        self.progress_range = progress_range
    
    def getSubRange(self, start, end):
        progress_range = (self.scaleProgress(start), self.scaleProgress(end))
        return Status(filename=self.filename, podclient=self.podclient, status=self.status, progress_range=progress_range)
    
    def scaleProgress(self, progress):
        return int(
            self.progress_range[0]
            + progress*(self.progress_range[1] - self.progress_range[0])/100
            )


    def __call__(self, status=None, progress=None, article=None, auto_dump=True,
        **kwargs):
        if status is not None and status != self.status.get('status'):
            log('STATUS: %s' % status)
            self.status['status'] = status
        
        if progress is not None:
            progress = min(max(0, progress), 100)
            progress = self.scaleProgress(progress)
            if progress > self.status.get('progress', -1):
                log('PROGRESS: %d%%' % progress)
                self.status['progress'] = progress
        
        if article is not None and article != self.status.get('article'):
            log('ARTICLE: %r' % article)
            self.status['article'] = article

        if self.podclient is not None:
            self.podclient.post_status(**self.status)
        
        sys.stdout.flush()
        
        self.status.update(kwargs)
        
        if auto_dump:
            self.dump()
    
    def dump(self):
        if not self.filename:
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
    
