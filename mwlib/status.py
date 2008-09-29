import simplejson
import sys

from mwlib.log import Log

log = Log('mwlib.statusfile')

class Status(object):
    def __init__(self,
        filename=None,
        podclient=None,
        progress_range=(0, 100),
        auto_dump=True,
    ):
        self.filename = filename
        self.podclient = podclient
        self.status = {}
        self.progress_range = progress_range
    
    def __call__(self, status=None, progress=None, article=None, auto_dump=True,
        **kwargs):
        if status is not None and status != self.status.get('status'):
            print 'STATUS: %s' % status
            self.status['status'] = status
        
        if progress is not None:
            assert 0 <= progress and progress <= 100, 'progress not in range 0..100'
            progress = int(
                self.progress_range[0]
                + progress*(self.progress_range[1] - self.progress_range[0])/100
            )
            if progress != self.status.get('progress'):
                print 'PROGRESS: %d%%' % progress
                self.status['progress'] = progress
        
        if article is not None and article != self.status.get('article'):
            print 'ARTICLE: %r' % article
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
            open(self.filename, 'wb').write(
                simplejson.dumps(self.status).encode('utf-8')
            )
        except Exception, exc:
            log.ERROR('Could not write status file %r: %s' % (
                self.filename, exc
            ))
    
