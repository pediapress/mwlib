import urllib

import mwlib.myjson as json


class Client(object):
    "HTTP client to mw-serve"

    def __init__(self, url):
        self.url = url

    def request(self, command, args):
        self.error = None
        post_data = dict(args)
        post_data['command'] = command
        f = urllib.urlopen(self.url, urllib.urlencode(post_data))
        self.response = json.loads(f.read())
        self.response_code = f.getcode()
        if self.response_code == 200:
            if 'error' in self.response:
                self.error = self.response['error']
                return False
        else:
            return False
        return True
