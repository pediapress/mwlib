#!/usr/bin/env python
# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.

"""main programs - installed via setuptools' entry_points"""
from optparse import OptionParser
import urllib
import urllib2
import time
import random
import simplejson
import mwlib.mwapidb
import mwlib.utils 
import mwlib.metabook


# disable fetch cache
mwlib.utils.fetch_url_orig = mwlib.utils.fetch_url 
def fetch_url(*args, **kargs):
    kargs["fetch_cache"] = {} 
    return mwlib.utils.fetch_url_orig(*args, **kargs) 
mwlib.utils.fetch_url = fetch_url


def getRandomArticles(api, min=1, max=100):
    #"http://en.wikipedia.org/w/api.php?action=query&list=random&rnnamespace=0&rnlimit=10"
    num = random.randint(min, max)
    articles = set()
    while len(articles) < num:
        res = api.query(list="random", rnnamespace=0, rnlimit=10)["random"]
        for x in res:
            articles.add(x["title"])
    return list(articles)[:max]


def getMetabook(articles):
    metabook = mwlib.metabook.make_metabook()
    metabook['title'] = u"title test"
    metabook['subtitle'] = u"sub title test"
    for a in articles:
        article = mwlib.metabook.make_article(title=a)
        metabook['items'].append(article)
    return metabook

def postCollection(metabook, baseurl, serviceurl, writer="rl"):
    data = {"metabook":simplejson.dumps(metabook), "writer":writer, "base_url":baseurl.encode('utf-8'), "command":"render"}
    data = urllib.urlencode(data)
    res =  urllib2.urlopen(urllib2.Request(serviceurl.encode("utf8"), data)).read()
    return simplejson.loads(res)

def getStatus(colid,serviceurl):
    data = urllib.urlencode({"command":"render_status", "collection_id":colid})
    res =  urllib2.urlopen(urllib2.Request(serviceurl.encode("utf8"), data)).read()
    return simplejson.loads(res)

def download(colid,serviceurl):
    data = urllib.urlencode({"command":"download", "collection_id":colid})
    return urllib2.urlopen(urllib2.Request(serviceurl.encode("utf8"), data)) # fh

def reportError(metabook, res):
    print "had error with collection", repr(metabook)
    print "error:"
    print res["error"]
    # FIXME REPORT ERROR and ARTICLES

def checkservice(api, serviceurl, baseurl, maxarticles):
    arts = getRandomArticles(api, min=1, max=maxarticles)
    metabook = getMetabook(arts)
    res = postCollection(metabook, baseurl, serviceurl)
    while True:
        time.sleep(1)
        res = getStatus(res["collection_id"], serviceurl)
        if res["state"] != "progress":
            break
    if res["state"] == "finished":
        d = download(res["collection_id"], serviceurl).read()
        # FIXME DO SOME CHECKS
        print "received PDF with %d bytes" % len(d)
    else: # error?
        assert res["state"] == "failed"
        reportError(metabook, res)

    

def main():
    parser = OptionParser(usage="%prog [OPTIONS]")
    parser.add_option("-b", "--baseurl", help="baseurl of wiki")
    parser.add_option('-l', '--logfile',help='log output to LOGFILE')
    parser.add_option('-m', '--max-narticles',
                      help='maximum number of articles for random collections (min is 1)',
                      default=10,
    )
    parser.add_option('-s', '--serviceurl',
                      help="location of the mw-serv server to test",
                      default='http://tools.pediapress.com/mw-serve/',
                      #default='http://localhost:8899/mw-serve/',
    )
    use_help = 'Use --help for usage information.'
    options, args = parser.parse_args()   
    api =  mwlib.mwapidb.APIHelper(options.baseurl)
    maxarts = int(getattr(options, "max-narticles", 10))
    while True:
        checkservice(api, options.serviceurl, options.baseurl, maxarts)
        # FIXME ALSO ENCAPSULATE THIS AND REPORT ERRORS
                            


if __name__ == '__main__':
    main()
