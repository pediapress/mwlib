from twisted.internet import reactor
from mwlib import podclient
from twisted.web import client 

class PODClient(podclient.PODClient):
    nextdata = None
    running = False
    def _post(self, data, content_type=None):
        if content_type is None:
            content_type = "application/x-www-form-urlencoded"
            headers = {'Content-Type': content_type}
        else:
            headers =  {}
            
        
        def postit(postdata, headers):
            client.getPage(self.posturl, method="POST", postdata=postdata, headers=headers).addCallbacks(done, done)
        
        def done(val):
            if self.nextdata:
                postdata, headers = self.nextdata
                self.nextdata = None
                reactor.callLater(0.0, postit, postdata, headers)
            else:
                self.running = False
                
        self.nextdata = (data, headers)
        if self.running:
            return
        
        self.running = True
        reactor.callLater(0.0, postit, data, headers)
