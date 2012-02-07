#!/usr/bin/env python
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

from optparse import OptionParser
import os
import urllib
import urllib2
import tempfile
import time
import random
import subprocess
import sys
try:
    import simplejson as json
except ImportError:
    import json

from mwlib import mwapidb, utils, log, bookshelf
import mwlib.metabook


RENDER_TIMEOUT_DEFAULT = 60*60 # 60 minutes
LICENSE_URL = 'http://en.wikipedia.org/w/index.php?title=Wikipedia:Text_of_the_GNU_Free_Documentation_License&action=raw'

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
    steps = (1+num/10)
    print num, steps
    for i in range(steps):
        res = api.query(list="random", rnnamespace=0, rnlimit=10)
        if res is None or 'query' not in res:
            print res
            time.sleep(5)
            continue
        res = res["query"]["random"]
        for x in res:
            articles.add(x["title"])
    return list(articles)[:max]


def getMetabook(articles):
    metabook = mwlib.metabook.collection()
    metabook.title = u"title test"
    metabook.subtitle = u"sub title test"
    for a in articles:
        article = mwlib.metabook.article(title=a)
        metabook.items.append(article)
    addLicense(metabook)
    return metabook


def getRandomMetabook(api, min=1, max=100):
    b = bookshelf.Bookshelf(api)
    booknames = b.booknames()
    num_articles = -1
    mbook = None
    tries = 100
    while tries and num_articles > max or num_articles < min:
        tries -=1
        if tries == 0:
            return None
        bn = random.choice(booknames)
        log.info("getRandomMetabook trying %r" % bn)
        c = api.content_query(bn)
        if not c:
            continue
        mbook = mwlib.metabook.parse_collection_page(c)
        num_articles = len(mbook.articles())
        log.info("getRandomMetabook num arts min:%d this:%d max:%d" % (min, num_articles, max))
    mbook['book_page'] = bn
    addLicense(mbook)
    return mbook

def addLicense(mbook):
    license_text = utils.fetch_url(
        LICENSE_URL,
        ignore_errors=False,
        expected_content_type='text/x-wiki',
        )
    license_text = unicode(license_text, 'utf-8')
    license = { 'mw_rights_text': license_text,
                'name': 'GNU Free Documentation License',
                }
    mbook['licenses'] = [license]

def postRenderCommand(metabook, baseurl, serviceurl, writer):
    log.info('POSTing render command %s %s' % (baseurl, writer))
    data = {
        "metabook": json.dumps(metabook),
        "writer": writer,
        "writer_options": writer_options.get(writer, ''),
        "base_url": baseurl.encode('utf-8'),
        "command":"render",
    }
    data = urllib.urlencode(data)
    res = urllib2.urlopen(urllib2.Request(serviceurl.encode("utf8"), data)).read()
    return json.loads(unicode(res, 'utf-8'))

def postRenderKillCommand(collection_id, serviceurl, writer):
    log.info('POSTing render_kill command %r' % collection_id)
    data = {
        "collection_id": collection_id,
        "writer": writer,
        "command":"render_kill",
    }
    data = urllib.urlencode(data)
    res = urllib2.urlopen(urllib2.Request(serviceurl.encode("utf8"), data)).read()
    return json.loads(unicode(res, 'utf-8'))

def getRenderStatus(colid, serviceurl, writer):
    #log.info('get render status')
    data = urllib.urlencode({"command": "render_status", "collection_id": colid, 'writer': writer})
    res = urllib2.urlopen(urllib2.Request(serviceurl.encode("utf8"), data)).read()
    return json.loads(unicode(res, 'utf-8'))

def download(colid, serviceurl, writer):
    log.info('download')
    data = urllib.urlencode({"command": "download", "collection_id": colid, 'writer': writer})
    return urllib2.urlopen(urllib2.Request(serviceurl.encode("utf8"), data)) # fh

def reportError(command, metabook, res, baseurl, writer,
    from_email=None,
    mail_recipients=None,
):
    utils.report(
        system=system,
        subject='Error %r with command %r' % (res.get('reason', '?'), command),
        error=res.get('error'),
        res=res,
        metabook=metabook,
        baseurl=baseurl,
        writer=writer,
        from_email=from_email,
        mail_recipients=mail_recipients,
    )
    sys.exc_clear()

def checkDoc(data, writer):
    log.info('checkDoc %s' % writer)
    assert len(data) > 0
    if writer == 'rl':
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

def checkservice(api, serviceurl, baseurl, writer, maxarticles,
                 from_email=None,
                 mail_recipients=None,
                 render_timeout = RENDER_TIMEOUT_DEFAULT # seconds or None
                 ):
#    arts = getRandomArticles(api, min=1, max=maxarticles)
#    log.info('random articles: %r' % arts)
#    metabook = getMetabook(arts)
    metabook = getRandomMetabook(api, min=5, max=maxarticles)
    if not metabook:
        reportError('render', metabook, dict(reason="getRandomMetabook Failed"), baseurl, writer,
                    from_email=from_email,
                    mail_recipients=mail_recipients)
        time.sleep(60)
                    
    res = postRenderCommand(metabook, baseurl, serviceurl, writer)
    collection_id = res['collection_id']
    st = time.time()
    while True:
        time.sleep(1)
        res = getRenderStatus(res["collection_id"], serviceurl, writer)
        if res["state"] != "progress":
            break
        if render_timeout and (time.time()-st) > render_timeout:
            log.timeout('Killing render proc for collection ID %r' % collection_id)
            r = postRenderKillCommand(collection_id, serviceurl, writer)
            if r['killed']:
                log.info('Killed.')
            else:
                log.warn('Nothing to kill!?')
            res["state"] = "failed"
            res["reason"] = "render_timeout (%ds)" % render_timeout
            break
    if res["state"] == "finished":
        d = download(res["collection_id"], serviceurl, writer).read()
        log.info("received %s document with %d bytes" % (writer, len(d)))        
        checkDoc(d, writer)
        return True
    else:
        reportError('render', metabook, res, baseurl, writer,
            from_email=from_email,
            mail_recipients=mail_recipients,
        )
    return False

    

def main():
    parser = OptionParser(usage="%prog [OPTIONS]")
    parser.add_option("-b", "--baseurl", help="baseurl of wiki")
    parser.add_option("-w", "--writer", help="writer to use")
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
    
    assert options.from_email

    if options.logfile:
        utils.start_logging(options.logfile)

    baseurl2api = {}
    baseurls = options.baseurl.split()
    for baseurl in baseurls:
        baseurl2api[baseurl] = mwapidb.APIHelper(baseurl)
    
    maxarts = int(options.max_narticles)
    mail_recipients = None
    if options.mail_recipients:
        mail_recipients = options.mail_recipients.split(',')
    ok_count = 0
    fail_count = 0
    while True:
        baseurl = random.choice(baseurls)
        try:
            ok = checkservice(baseurl2api[baseurl],
                options.serviceurl,
                baseurl,
                options.writer,
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
                subject='checkservice() failed, waiting 60seconds',
                from_email=options.from_email,
                mail_recipients=mail_recipients,
            )
            sys.exc_clear()
            time.sleep(60)
        log.info('%s, %s\tok: %d, failed: %d' % (
            baseurl, options.writer, ok_count, fail_count,
        ))


if __name__ == '__main__':
    #print getRandomMetabook(mwapidb.APIHelper("http://en.wikipedia.org/w"), min=10, max=20)
    main()
    
