"""Client to a Print-on-Demand partner service (e.g. pediapress.com)"""



import os
import time
import six.moves.urllib.parse
import six.moves.urllib.request, six.moves.urllib.parse, six.moves.urllib.error
import six.moves.urllib.request, six.moves.urllib.error, six.moves.urllib.parse
import six.moves.http_client
import six

try:
    import simplejson as json
except ImportError:
    import json

from mwlib.log import Log
from mwlib.utils import get_multipart
from mwlib import conf

log = Log("mwapidb")


class PODClient:
    def __init__(self, posturl, redirecturl=None):
        self.posturl = posturl.encode('utf-8')
        self.redirecturl = redirecturl

    def _post(self, data, content_type=None):
        if content_type is not None:
            headers = {'Content-Type': content_type}
        else:
            headers = {}
        return six.moves.urllib.request.urlopen(six.moves.urllib.request.Request(self.posturl, data, headers=headers)).read()

    def post_status(self, status=None, progress=None, article=None, error=None):
        post_data = {}

        def setv(name, val):
            if val is None:
                return
            if not isinstance(val, str):
                val = val.encode("utf-8")
            post_data[name] = val

        setv("status", status)
        setv("error", error)
        setv("article", article)

        if progress is not None:
            post_data['progress'] = '%d' % progress

        self._post(six.moves.urllib.parse.urlencode(post_data))

    def streaming_post_zipfile(self, filename, fh=None):
        if fh is None:
            fh = open(filename, "rb")

        boundary = "-" * 20 + ("%f" % time.time()) + "-" * 20

        items = []
        items.append("--" + boundary)
        items.append('Content-Disposition: form-data; name="collection"; filename="collection.zip"')
        items.append('Content-Type: application/octet-stream')
        items.append('')
        items.append('')

        before = "\r\n".join(items)

        items = []
        items.append('')
        items.append('--' + boundary + '--')
        items.append('')
        after = "\r\n".join(items)

        clen = len(before) + len(after) + os.path.getsize(filename)

        print("POSTING TO:", self.posturl)

        pr = six.moves.urllib.parse.urlparse(self.posturl)
        path = pr.path
        if pr.query:
            path += "?" + pr.query

        h = six.moves.http_client.HTTP(pr.hostname, pr.port)
        h.putrequest("POST", path)
        h.putheader("Host", pr.netloc)
        h.putheader("Content-Length", str(clen))
        h.putheader("User-Agent", conf.user_agent)
        h.putheader("Content-Type", "multipart/form-data; boundary=%s" % boundary)
        h.endheaders()

        h.send(before)

        while True:
            data = fh.read(4096)
            if not data:
                break
            h.send(data)

        h.send(after)

        errcode, errmsg, headers = h.getreply()
        # h.file.read()
        print("ERRCODE:", (errcode, errmsg, headers))

        if errcode != 200:
            raise RuntimeError("upload failed: %r" % (errmsg,))

    def post_zipfile(self, filename):
        f = open(filename, "rb")
        content_type, data = get_multipart('collection.zip', f.read(), 'collection')
        f.close()
        log.info('POSTing zipfile %r to %s (%d Bytes)' % (filename, self.posturl, len(data)))
        self._post(data, content_type=content_type)


def podclient_from_serviceurl(serviceurl):
    result = json.loads(six.text_type(six.moves.urllib.request.urlopen(serviceurl, data="any").read(), 'utf-8'))
    return PODClient(result["post_url"], redirecturl=result["redirect_url"])
