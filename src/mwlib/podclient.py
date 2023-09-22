"""Client to a Print-on-Demand partner service (e.g. pediapress.com)"""


import os
import time

import six
import six.moves.http_client
import six.moves.urllib.error
import six.moves.urllib.parse
import six.moves.urllib.request

try:
    import simplejson as json
except ImportError:
    import json

from mwlib import conf
from mwlib.log import Log
from mwlib.utils import get_multipart

log = Log("mwapidb")


class PODClient:
    def __init__(self, posturl, redirecturl=None):
        self.posturl = posturl.encode("utf-8")
        self.redirecturl = redirecturl

    def _post(self, data, content_type=None):
        headers = {"Content-Type": content_type} if content_type is not None else {}
        return six.moves.urllib.request.urlopen(
            six.moves.urllib.request.Request(self.posturl, data,
                                             headers=headers)
        ).read()

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
            post_data["progress"] = "%d" % progress

        self._post(six.moves.urllib.parse.urlencode(post_data))

    def streaming_post_zipfile(self, filename, file_handler=None):
        if file_handler is None:
            file_handler = open(filename, "rb")

        boundary = "-" * 20 + ("%f" % time.time()) + "-" * 20

        items = []
        items.append("--" + boundary)
        items.append(
            'Content-Disposition: form-data; name="collection"; filename="collection.zip"'
        )
        items.append("Content-Type: application/octet-stream")
        items.append("")
        items.append("")

        before = "\r\n".join(items)

        items = []
        items.append("")
        items.append("--" + boundary + "--")
        items.append("")
        after = "\r\n".join(items)

        clen = len(before) + len(after) + os.path.getsize(filename)

        print("POSTING TO:", self.posturl)

        parsed_url = six.moves.urllib.parse.urlparse(self.posturl)
        path = parsed_url.path
        if parsed_url.query:
            path += "?" + parsed_url.query

        http = six.moves.http_client.HTTP(parsed_url.hostname, parsed_url.port)
        http.putrequest("POST", path)
        http.putheader("Host", parsed_url.netloc)
        http.putheader("Content-Length", str(clen))
        http.putheader("User-Agent", conf.user_agent)
        http.putheader("Content-Type",
                    "multipart/form-data; boundary=%s" % boundary)
        http.endheaders()

        http.send(before)

        while True:
            data = file_handler.read(4096)
            if not data:
                break
            http.send(data)

        http.send(after)

        errcode, errmsg, headers = http.getreply()
        # h.file.read()
        print("ERRCODE:", (errcode, errmsg, headers))

        if errcode != 200:
            raise RuntimeError(f"upload failed: {errmsg!r}")

    def post_zipfile(self, filename):
        with open(filename, "rb") as zip_file:
            content_type, data = get_multipart("collection.zip", zip_file.read(),
                                               "collection")
        log.info(
            "POSTing zipfile %r to %s (%d Bytes)" % (filename, self.posturl,
                                                     len(data))
        )
        self._post(data, content_type=content_type)


def podclient_from_serviceurl(serviceurl):
    result = json.loads(
        six.text_type(
            six.moves.urllib.request.urlopen(serviceurl, data="any").read(),
            "utf-8"
        )
    )
    return PODClient(result["post_url"], redirecturl=result["redirect_url"])
