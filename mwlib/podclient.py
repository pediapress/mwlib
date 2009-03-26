"""Client to a Print-on-Demand partner service (e.g. pediapress.com)"""

import urllib
import urllib2

try:
    import json
except ImportError:
    import simplejson as json

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
    
    def post_status(self, status=None, progress=None, article=None):
        post_data = {}
        if status is not None:
            if not isinstance(status, str):
                status = status.encode('utf-8')
            post_data['status'] = status
        if progress is not None:
            post_data['progress'] = '%d' % progress
        if article is not None:
            if not isinstance(article, str):
                article = article.encode('utf-8')
            post_data['article'] = article
        self._post(urllib.urlencode(post_data))
    
    def post_zipfile(self, filename):
        f = open(filename, "rb")
        content_type, data = get_multipart('collection.zip', f.read(), 'collection')
        f.close()
        log.info('POSTing zipfile %r to %s (%d Bytes)' % (filename, self.posturl, len(data)))
        self._post(data, content_type=content_type)

def podclient_from_serviceurl(serviceurl):
    result = json.loads(unicode(urllib2.urlopen(serviceurl, data="any").read(), 'utf-8'))
    return PODClient(result["post_url"], redirecturl=result["redirect_url"])
