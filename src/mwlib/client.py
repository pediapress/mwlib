from __future__ import absolute_import

import six.moves.urllib.error
import six.moves.urllib.parse
import six.moves.urllib.request

import mwlib.myjson as json


class Error(Exception):
    pass


class Client(object):
    """HTTP client to mw-serve"""

    def __init__(self, url):
        self.url = url
        self.response = None

    def request(self, command, args, is_json=True):
        self.error = None
        post_data = dict(args)
        post_data["command"] = command
        f = six.moves.urllib.request.urlopen(self.url, six.moves.urllib.parse.urlencode(post_data))
        self.response = f.read()
        self.response_code = f.getcode()
        if self.response_code != 200:
            raise Error(self.response)

        if is_json:
            self.response = json.loads(self.response)
            if "error" in self.response:
                self.error = self.response["error"]
                raise Error(self.error)

        return self.response
