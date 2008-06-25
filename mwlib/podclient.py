"""Client to a Print-on-Demand partner service (e.g. pediapress.com)"""

import urllib
import urllib2

import simplejson

from mwlib.log import Log
from mwlib.utils import get_multipart

log = Log("mwapidb")

class PODClient(object):
    def __init__(self, posturl, redirecturl=None):
        self.posturl = posturl.encode('utf-8')
        self.redirecturl = redirecturl
    
    def _post(self, data, content_type=None):
        if content_type is not None:
            headers = {'Content-Type': content_type}
        else:
            headers = {}
        return urllib2.urlopen(urllib2.Request(self.posturl, data, headers=headers)).read()
    
    def post_status(self, status):
        self._post(urllib.urlencode({'status': str(status)}))
    
    def post_progress(self, progress):
        self._post(urllib.urlencode({'progress': '%d' % progress}))
    
    def post_current_article(self, title):
        self._post(urllib.urlencode({'article': title.encode('utf-8')}))

    def post_zipfile(self, filename):
        f = open(filename, "rb")
        content_type, data = get_multipart('collection.zip', f.read(), 'collection')
        f.close()
        log.info('POSTing zipfile %r to %s (%d Bytes)' % (filename, self.posturl, len(data)))
        self._post(data, content_type=content_type)

def podclient_from_serviceurl(serviceurl):
    result = simplejson.loads(urllib2.urlopen(serviceurl, data="any").read())
    return PODClient(result["post_url"], redirecturl=result["redirect_url"])
