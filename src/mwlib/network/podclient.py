"""Client to a Print-on-Demand partner service (e.g. pediapress.com)"""

import http.client
import logging
import os
import time
import urllib.parse

import requests

try:
    import simplejson as json
except ImportError:
    import json

from mwlib.utils import conf
from mwlib.utils.unorganized import get_multipart

log = logging.getLogger(__name__)


class PODClient:
    def __init__(self, posturl, redirecturl=None):
        self.posturl = posturl.encode("utf-8")
        self.redirecturl = redirecturl

    def _post(self, data, content_type=None):
        headers = {"Content-Type": content_type} if content_type is not None else {}
        print("POSTING TO:", self.posturl)
        jdata = json.dumps(data).encode("utf-8")
        return requests.post(self.posturl, data=jdata, headers=headers).content

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

        encoded_post_data = urllib.parse.urlencode(post_data)
        self._post(encoded_post_data)

    def streaming_post_zipfile(self, filename, file_handler=None):
        with file_handler if file_handler else open(filename, "rb") as file_handler:
            boundary = "-" * 20 + ("%f" % time.time()) + "-" * 20

            items = []
            items.append("--" + boundary)
            items.append(
                'Content-Disposition: form-data; name="collection"; filename="collection.zip"'
            )
            items.append("Content-Type: application/octet-stream")
            items.append("")
            items.append("")

            before = "\r\n".join(items).encode("utf-8")  # Convert to bytes

            items = []
            items.append("")
            items.append("--" + boundary + "--")
            items.append("")
            after = "\r\n".join(items).encode("utf-8")  # Convert to bytes

            clen = len(before) + len(after) + os.path.getsize(filename)

            print("POSTING TO:", self.posturl)

            parsed_url = urllib.parse.urlparse(self.posturl)
            path = parsed_url.path.decode("utf-8")
            if parsed_url.query:
                path += "?" + parsed_url.query.decode("utf-8")
            path = path.encode("utf-8")
            http_data = http.client.HTTPConnection(parsed_url.hostname.decode("utf-8"))
            path = path.decode("utf-8")
            http_data.putrequest("POST", path)
            http_data.putheader("Host", parsed_url.netloc)
            http_data.putheader("Content-Length", str(clen))
            http_data.putheader(
                "User-Agent", conf.user_agent
            )  # assuming conf.user_agent is defined
            http_data.putheader("Content-Type", f"multipart/form-data; boundary={boundary}")
            http_data.endheaders()

            http_data.send(before)

            while True:
                data = file_handler.read(4096)
                if not data:
                    break
                http_data.send(data)

            http_data.send(after)

            while True:
                data = file_handler.read(4096)
                if not data:
                    break
                http_data.send(data)

            http_data.send(after)
            response = http_data.getresponse()
            status_code = response.status
            reason = response.reason
            headers = response.getheaders()
            print("Response:", (status_code, reason, headers))
            if status_code != 200:
                raise RuntimeError(f"Upload failed: {reason!r}")

    def post_zipfile(self, filename):
        with open(filename, "rb") as zip_file:
            content_type, data = get_multipart(
                "collection.zip", zip_file.read(), "collection"
            )
        log.info(
            "POSTing zipfile %r to %s (%d Bytes)" % (filename, self.posturl, len(data))
        )
        self._post(data, content_type=content_type)


def podclient_from_serviceurl(serviceurl):
    response = requests.post(serviceurl, data=b"any").json()
    return PODClient(response["post_url"], redirecturl=response["redirect_url"])
