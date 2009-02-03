
# based on code by Raymond Hettinger
# see http://code.activestate.com/recipes/498245/

import threading
from collections import deque

class lrucache(object):
    def __init__(self, maxsize):
        self.maxsize = maxsize
        self.cache = {}
        self.queue = deque()         # order that keys have been accessed
        self.refcount = {}           # number of times each key is in the access queue
        self.hits = 0
        self.misses = 0
        
    def __getitem__(self, key):
        # get cache entry or compute if not found
        try:
            result = self.cache[key]
            self.hits += 1
            self._record_key(key)
            return result
        except KeyError:
            self.misses += 1
            raise

    def __setitem__(self, key, value):
        self.cache[key] = value
        self._record_key(key)
        
    def _record_key(self, key):
        # localize variable access (ugly but fast)
        queue=self.queue
        cache=self.cache
        _len=len
        refcount=self.refcount
        _maxsize=self.maxsize
        queue_append=self.queue.append
        queue_popleft = self.queue.popleft
        
        # record that this key was recently accessed
        self.queue.append(key)
        self.refcount[key] = self.refcount.get(key, 0) + 1

        # Purge least recently accessed cache contents
        while _len(cache) > _maxsize:
            k = queue_popleft()
            refcount[k] -= 1
            if not refcount[k]:
                del cache[k]
                del refcount[k]

        # Periodically compact the queue by duplicate keys
        if _len(queue) > _maxsize * 4:
            for i in [None] * _len(queue):
                k = queue_popleft()
                if refcount[k] == 1:
                    queue_append(k)
                else:
                    refcount[k] -= 1

class mt_lrucache(lrucache):
    def __init__(self, maxsize):
        lrucache.__init__(self, maxsize)
        self.lock = threading.Lock()
        
    def __getitem__(self, key):
        try:
            self.lock.acquire()
            return lrucache.__getitem__(self, key)
        finally:
            self.lock.release()

    def __setitem__(self, key, val):
        try:
            self.lock.acquire()
            lrucache.__setitem__(self, key, val)
        finally:
            self.lock.release()            
