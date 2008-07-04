import atexit
import Queue
import threading
import time
import traceback

from mwlib.log import Log
from mwlib import utils

log = Log('mwlib.fetcher')

# ==============================================================================


class Fetcher(object):
    """Fetch URLs in parallel"""
    
    def __init__(self, num_threads=5):
        """
        @param num_threads: number of threads to start for fetching
        @type num_threads: int
        """
        
        self.num_threads = num_threads        
        self.job_queue = Queue.Queue()
        self.results = {}
        self.started = False
        self.last_fetch = time.time()
    
    def fetch_url(self, url, filename=None, opener=None, callback=None):
        """Fetch given URL
        
        @param url: URL to fetch
        @type url: str
        
        @param filename: if given, write fetched content to file with filename
        @type filename: basestring
        
        @param opener: if given, use this opener to fetch the URL
        @type opener: L{urlib2.OpenerDirector}
        """
        
        print 'FROM LAST FETCH', time.time() - self.last_fetch
        self.last_fetch = time.time()
        print 'QUEUE SIZE', self.job_queue.qsize()
        
        if not self.started:
            self.started = True
            for i in range(self.num_threads):
                FetcherThread(self).start()
            atexit.register(self.kill_threads)
        self.job_queue.put({
            'url': url,
            'filename': filename,
            'opener': opener,
            'callback': callback,
        })
    
    def get_results(self):
        """Wait for all queued fetch_url() requests to be finished and return
        results as dictionary mapping URLs to
         * fetched content if filename arg of fetch_url() was None and the
           content could be retrieved
         * True if filename arg of fetch_url() was not None and the content
           could be retrieved (it's written to the file with given filename)
         * None if the URL could not be retrieved
         
        @returns: dictionary containing results
        @rtype: dict
        """
        
        self.kill_threads()
        return self.results
    
    def kill_threads(self):
        if not self.started:
            return
        for i in range(self.num_threads):
            self.job_queue.put({'url': 'die'})
        self.job_queue.join()
        self.started = False
    

# ==============================================================================


class FetcherThread(threading.Thread):
    def __init__(self, fetcher):
        super(FetcherThread, self).__init__()
        self.fetcher = fetcher
    
    def run(self):
        while True:
            d = self.fetcher.job_queue.get()
            url = d.get('url')
            try:
                if url == 'die':
                    break
                try:                
                    result = utils.fetch_url(url,
                        ignore_errors=True,
                        opener=d.get('opener'),
                    )
                    if result is None:
                        continue
                    callback = d.get('callback')
                    filename = d.get('filename')
                    if callback:
                        callback(url, result)
                    elif filename:
                        open(filename, 'wb').write(result)
                        self.fetcher.results[url] = True
                    else:
                        self.fetcher.results[url] = result
                except Exception, exc:
                    log.ERROR('Could not fetch url %r: %s' % (url, exc))
                    traceback.print_exc()
            finally:
                self.fetcher.job_queue.task_done()        
    

# ==============================================================================

if __name__ == '__main__':
    for n in [1, 5]:
        s = time.time()
        f = Fetcher(num_threads=n)
        for url in [
            'http://brainbot.com/',
            'http://pediapress.com/',
            'http://python.org/',
            'http://mediawiki.org/',
            'http://en.wikipedia.org/',
            'http://de.wikipedia.org/',
            'http://fr.wikipedia.org/',
            'http://es.wikipedia.org/',
            'http://it.wikipedia.org/',
            'http://zh.wikipedia.org/',
        ]:
            f.fetch_url(url)
        results = f.get_results()
        for url, content in results.items():
            print url, len(content)
        print time.time() - s
    
