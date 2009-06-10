
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.txt for additional licensing information.

from mwlib.net import fetch, mwapi
from mwlib.metabook import get_licenses
from twisted.internet import reactor,  defer

class start_fetcher(object):
    def __init__(self, **kw):
        self.fetcher = None
        self.__dict__.update(kw)
        
    def get_api(self):
        api = mwapi.mwapi(self.api_url)
        if self.username:
            return api.login(self.username, self.password, self.domain)
        return defer.succeed(api)

    def fetch_pages_from_metabook(self,  api):
        fsout = self.fsout
        metabook=self.metabook
        
        fsout.dump_json(metabook=metabook)
        nfo = {
            'format': 'nuwiki',
            'base_url': self.base_url,
            'script_extension': self.options.script_extension,
        }
        if self.options.print_template_pattern:
            nfo["print_template_pattern"] = self.options.print_template_pattern

        fsout.dump_json(nfo=nfo)

        pages = fetch.pages_from_metabook(metabook)
        self.fetcher = fetch.fetcher(api, fsout, pages,
                                     licenses=self.licenses,
                                     podclient=self.podclient,
                                     print_template_pattern=self.options.print_template_pattern,
                                     template_exclusion_category=self.options.template_exclusion_category,
                                     imagesize=self.options.imagesize)
        
    def run(self):
        base_url = self.base_url
        options = self.options
        metabook = self.metabook
        
        if not base_url.endswith("/"):
            base_url += "/"
        api_url = "".join([base_url, "api", options.script_extension])
        if isinstance(api_url,  unicode):
            api_url = api_url.encode("utf-8")
        self.api_url = api_url
        
        login = options.login
        username, password, domain = None, None, None
        if login:
            if login.count(':') == 1:
                username, password = unicode(login, 'utf-8').split(':', 1)
            else:
                username, password, domain = unicode(login, 'utf-8').split(':', 2)

        self.username,  self.password,  self.domain = username,  password,  domain
        
        self.fsout = fetch.fsoutput(self.fsdir)

        self.licenses = get_licenses(metabook)
        podclient = self.podclient

        def start():
            def login_failed(res):
                print "Fatal error: login failed:", res.getErrorMessage()
                reactor.stop()
                return res
            self.get_api().addErrback(login_failed).addCallback(self.fetch_pages_from_metabook)

        try:
            if podclient is not None:
                old_class = podclient.__class__
                podclient.__class__ = fetch.PODClient

            reactor.callLater(0.0, start)
            reactor.run()
        finally:
            if podclient is not None:
                podclient.__class__ = old_class


        fetcher = self.fetcher
        if not fetcher:
            raise RuntimeError("Fatal error")

        if fetcher.fatal_error:
            print "error:", fetcher.fatal_error
            raise RuntimeError('Fatal error')
        print "done"




def make_nuwiki(fsdir, base_url, metabook, options, podclient=None):
    sf = start_fetcher(fsdir=fsdir, base_url=base_url, metabook=metabook, options=options, podclient=podclient)
    sf.run()
