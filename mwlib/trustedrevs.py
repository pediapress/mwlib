#! /usr/bin/env python

import mwclient
import urllib2
import time

class WikiTrustServerError(Exception):
    "For some reason the API often respons with an error"
    msg_identifier = 'EERROR detected.  Try again in a moment, or report an error on the WikiTrust bug tracker.'

class TrustedRevisions(object):
    min_trust = 0.80
    wikitrust_api = 'http://en.collaborativetrust.com/WikiTrust/RemoteAPI'
    
    def __init__(self, site_name = 'en.wikipedia.org'):
            self.site = mwclient.Site(site_name)
        
    def getWikiTrustScore(self, title, revid):
        # http://en.collaborativetrust.com/WikiTrust/RemoteAPI?method=quality&title=Buster_Keaton&pageid=43055&revid=364710354
        url = '%s?method=quality&title=%s&revid=%d' % \
                (self.wikitrust_api, urllib2.quote(title), revid)
        r = urllib2.urlopen(url).read()
        if r == WikiTrustServerError.msg_identifier:
            raise WikiTrustServerError
        return 1 - float(r) # r is the likelyhood of being spam 
        
            
    def getTrustedRevision(self, title, min_trust=None, max_age=None):
        min_trust = min_trust or self.min_trust
        best_rev = None
        now = time.time() 
        p= self.site.Pages[title]
        for rev in p.revisions():
            #add basic info
            rev['age'] = (now - time.mktime(rev['timestamp']))/(24*3600) # days
            rev['title'] = title
            
            # don't use bot revs
            if 'bot' in rev['user'].lower(): 
                continue
            # don't use reverted revs (but rather the original one)
            if 'revert' in rev.get('comment','').lower():
                continue
            
            try:
                rev['score'] = self.getWikiTrustScore(title, rev['revid'])
            except WikiTrustServerError:
                #print '%s\t%d\terror' %(title, rev['revid'])
                continue
            
            #print '%s\t%d\t%.2f' %(title, rev['revid'], rev['score'])            
            if not best_rev or rev['score'] > best_rev['score']:
                best_rev = rev
            if rev['score'] > min_trust: # break if we have a sufficient score    
                break
            if max_age and rev['age'] > max_age: # break if articles get too old
                break
            
        return best_rev
        
        
if __name__ == '__main__':
    import sys
    tr = TrustedRevisions()
    trev = tr.getTrustedRevision(sys.argv[1])
    print 'Found revision:', trev
    print 'title:%s revid:%d age:%.2f days' %(trev['title'], trev['revid'], trev['age'])
