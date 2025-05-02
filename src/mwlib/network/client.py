import urllib.error
import urllib.parse
import urllib.request

import mwlib.utils.myjson as json


class Error(Exception):
    pass


class Client:
    """HTTP client to mw-serve"""

    def __init__(self, url):
        self.url = url
        self.response = None
        self.error = None
        self.response_code = None

    def request(self, command, args, is_json=True):
        self.error = None
        post_data = dict(args)
        post_data["command"] = command
        url_file = urllib.request.urlopen(
            self.url, urllib.parse.urlencode(post_data)
        )
        self.response = url_file.read()
        self.response_code = url_file.getcode()
        if self.response_code != 200:
            raise Error(self.response)

        if is_json:
            self.response = json.loads(self.response)
            if "error" in self.response:
                self.error = self.response["error"]
                raise Error(self.error)

        return self.response
