#!/usr/bin/env python
# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.

from optparse import OptionParser
import os
import urllib
import urllib2
import tempfile
import time
import random
import simplejson
import subprocess

from mwlib import mwapidb, utils, log
import mwlib.metabook

system = 'mw-serve-stresser'

log = log.Log('mw-serve-stresser')

# disable fetch cache
utils.fetch_url_orig = utils.fetch_url 
def fetch_url(*args, **kargs):
    kargs["fetch_cache"] = {} 
    return utils.fetch_url_orig(*args, **kargs) 
utils.fetch_url = fetch_url

writer_options = {
    'rl': 'strict',
}

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

def postRenderCommand(metabook, baseurl, serviceurl, writer="rl"):
    log.info('POSTing render command')
    data = {
        "metabook": simplejson.dumps(metabook),
        "writer": writer,
        "writer_options": writer_options.get(writer, ''),
        "base_url": baseurl.encode('utf-8'),
        "command":"render",
    }
    data = urllib.urlencode(data)
    res =  urllib2.urlopen(urllib2.Request(serviceurl.encode("utf8"), data)).read()
    return simplejson.loads(res)

def getRenderStatus(colid, serviceurl):
    log.info('get render status')
    data = urllib.urlencode({"command":"render_status", "collection_id":colid})
    res =  urllib2.urlopen(urllib2.Request(serviceurl.encode("utf8"), data)).read()
    return simplejson.loads(res)

def download(colid,serviceurl):
    log.info('download')
    data = urllib.urlencode({"command":"download", "collection_id":colid})
    return urllib2.urlopen(urllib2.Request(serviceurl.encode("utf8"), data)) # fh

def reportError(command, metabook, res,
    from_email=None,
    mail_recipients=None,
):
    utils.report(
        system=system,
        subject='Error with command %r' % command,
        error=res.get('error'),
        res=res,
        metabook=metabook,
        from_email=from_email,
        mail_recipients=mail_recipients,
    )

def checkPDF(data):
    log.info('checkPDF')
    fd, filename = tempfile.mkstemp(suffix='.pdf')
    os.write(fd, data)
    os.close(fd)
    try:
        popen = subprocess.Popen(args=['pdfinfo', filename], stdout=subprocess.PIPE)
        rc = popen.wait()
        assert rc == 0, 'pdfinfo rc = %d' % rc
        for line in popen.stdout:
            line = line.strip()
            if not line.startswith('Pages:'):
                continue
            num_pages = int(line.split()[-1])
            assert num_pages > 0, 'PDF is empty'
            break
        else:
            raise RuntimeError('invalid PDF')
    finally:
        os.unlink(filename)

def checkservice(api, serviceurl, baseurl, maxarticles,
    from_email=None,
    mail_recipients=None,
):
    arts = getRandomArticles(api, min=1, max=maxarticles)
    log.info('random articles: %r' % arts)
    metabook = getMetabook(arts)
    res = postRenderCommand(metabook, baseurl, serviceurl)
    while True:
        time.sleep(1)
        res = getRenderStatus(res["collection_id"], serviceurl)
        if res["state"] != "progress":
            break
    if res["state"] == "finished":
        d = download(res["collection_id"], serviceurl).read()
        checkPDF(d)
        print "received PDF with %d bytes" % len(d)
    else:
        reportError('render', metabook, res,
            from_email=from_email,
            mail_recipients=mail_recipients,
        )

    

def main():
    parser = OptionParser(usage="%prog [OPTIONS]")
    parser.add_option("-b", "--baseurl", help="baseurl of wiki")
    parser.add_option('-l', '--logfile', help='log output to LOGFILE')
    parser.add_option('-f', '--from-email',
        help='From: email address for error mails',
    )
    parser.add_option('-r', '--mail-recipients',
        help='To: email addresses ("," separated) for error mails',
    )
    parser.add_option('-m', '--max-narticles',
        help='maximum number of articles for random collections (min is 1)',
        default=10,
    )
    parser.add_option('-s', '--serviceurl',
        help="location of the mw-serve server to test",
        default='http://tools.pediapress.com/mw-serve/',
        #default='http://localhost:8899/mw-serve/',
    )
    use_help = 'Use --help for usage information.'
    options, args = parser.parse_args()   
    
    if options.logfile:
        utils.start_logging(options.logfile)
    
    api =  mwapidb.APIHelper(options.baseurl)
    maxarts = int(getattr(options, "max-narticles", 10))
    mail_recipients = None
    if options.mail_recipients:
        mail_recipients = options.mail_recipients.split(',')
    ok_count = 0
    fail_count = 0
    while True:
        try:
            ok = checkservice(api,
                options.serviceurl,
                options.baseurl,
                maxarts,
                from_email=options.from_email,
                mail_recipients=mail_recipients,
            )
            if ok:
                ok_count += 1
                log.check('OK')
            else:
                fail_count += 1
                log.check('FAIL!')
        except KeyboardInterrupt:
            break
        except:
            fail_count += 1
            log.check('EPIC FAIL!!!')
            utils.report(
                system=system,
                subject='checkservice() failed',
                from_email=options.from_email,
                mail_recipients=mail_recipients,
            )
        log.info('ok: %d, failed: %d' % (ok_count, fail_count))


if __name__ == '__main__':
    main()
