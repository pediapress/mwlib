
# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.

"""main programs - installed via setuptools' entry_points"""

import optparse

def buildcdb():
    parser = optparse.OptionParser(usage="%prog --input XMLDUMP --output OUTPUT")
    parser.add_option("-i", "--input", help="input file")
    parser.add_option("-o", "--output", help="write output to OUTPUT")
    options, args = parser.parse_args()
    
    if args:
        parser.error("too many arguments.")

    
    input = options.input
    output = options.output

    if not (input and output):
        parser.error("missing argument.")
        
    import os
    from mwlib import cdbwiki

    cdbwiki.BuildWiki(input, output)()
    open(os.path.join(output, "wikiconf.txt"), "w").write("""
[wiki]
type = cdb
path = %s

[images]
type = download
url = http://upload.wikimedia.org/wikipedia/commons/
localpath = ~/images
""" % (os.path.abspath(output),))

def show():
    parser = optparse.OptionParser()
    parser.add_option("-c", "--conf", help="config file")
    parser.add_option("-e", "--expand", action="store_true", help="expand templates")
    parser.add_option("-t", "--template", action="store_true", help="show template")
    parser.add_option("-f", help='read input from file. implies -e')
    
    options, args = parser.parse_args()
    
    if not args and not options.f:
        parser.error("missing ARTICLE argument")
        
    articles = [unicode(x, 'utf-8') for x in args]

    conf = options.conf
    if not conf:
        parser.error("missing --conf argument")

    from mwlib import wiki, expander
    
    db = wiki.makewiki(conf)['wiki']
    
    for a in articles:
        if options.template:
            raw=db.getTemplate(a)
        else:
            raw=db.getRawArticle(a)

        if raw:
            if options.expand:
                te = expander.Expander(raw, pagename=a, wikidb=db)
                raw = te.expandTemplates()

            print raw.encode("utf-8")
    if options.f:
        raw = unicode(open(options.f).read(), 'utf-8')
        te = expander.Expander(raw, pagename='test', wikidb=db)
        raw = te.expandTemplates()
        print raw.encode("utf-8")

def buildzip():
    parser = optparse.OptionParser(usage="%prog [OPTIONS] [ARTICLE ...]")
    parser.add_option("-c", "--conf", help="config file (required unless --baseurl is given)")
    parser.add_option("-b", "--baseurl", help="base URL for mwapidb backend")
    parser.add_option("-s", "--shared-baseurl", help="base URL for shared images for mwapidb backend")
    parser.add_option("-m", "--metabook", help="JSON encoded text file with book structure")
    parser.add_option('--collectionpage', help='Title of a collection page')
    parser.add_option("-x", "--noimages", action="store_true", help="exclude images")
    parser.add_option("-o", "--output", help="write output to OUTPUT")
    parser.add_option("-p", "--posturl", help="http post to POSTURL (directly)")
    parser.add_option("-g", "--getposturl", action="store_true", help="get posturl from pp and direct browser to upload url")
    parser.add_option("-i", "--imagesize",
                      help="max. pixel size (width or height) for images (default: 800)")
    parser.add_option("-d", "--daemonize", action="store_true",
                      help='become daemon after collection articles (before POST request)')
    parser.add_option("-l", "--logfile", help="log to logfile")
    parser.add_option("--license", help="Title of article containing full license text")
    parser.add_option("--template-blacklist", help="Title of article containing blacklisted templates")
    options, args = parser.parse_args()
    
    import tempfile
    import os
    import zipfile
    import simplejson
    from mwlib import utils
    from mwlib.utils import daemonize
    import urllib
    import urllib2

    articles = [unicode(x, 'utf-8') for x in args]
    
    baseurl = options.baseurl
    conf = options.conf
    if not baseurl and not options.conf:
        parser.error("neither --conf nor --baseurl specified\nuse --help for all options")
    
    posturl = None
    posturl = options.posturl
    if posturl:
        posturl = posturl.encode('utf-8')

    # automatically acquires a post url 
    if not posturl and options.getposturl:
        serviceurl = "http://pediapress.com/api/collections/"
        browsercmd = "firefox %s &"
        u = urllib2.urlopen(serviceurl, data="any")
        h = simplejson.loads(u.read())
        posturl = h["post_url"]
        redirect_url = h["redirect_url"]
        os.system(browsercmd % redirect_url)
        print "acquired post url", posturl
        print "redirected browser to", redirect_url


    def post_status(status):
        print 'status:', status
        if not posturl:
            return
        try:
            return urllib2.urlopen(posturl, urllib.urlencode({'status': status})).read()
        except Exception, e:
            print 'ERROR posting status %r to %r: %s' % (status, posturl, e)
    
    def post_progress(progress):
        progress = int(progress)
        print 'progress', progress
        if not posturl:
            return
        try:
            return urllib2.urlopen(posturl, urllib.urlencode({'progress': progress})).read()
        except Exception, e:
            print 'ERROR posting progress %d to %r: %s' % (progress, posturl, e)
    
    try:
        if options.logfile:
            utils.start_logging(options.logfile)
            
        output = options.output

        from mwlib import wiki, recorddb, metabook
        
        mb = metabook.MetaBook()
        if conf:
            from ConfigParser import ConfigParser

            w = wiki.makewiki(conf)
            cp = ConfigParser()
            cp.read(conf)
            mb.source = {
                'name': cp.get('wiki', 'name'),
                'url': cp.get('wiki', 'url'),
            }
            license_name = cp.get('wiki', 'defaultarticlelicense')
            if license_name is not None:
                wikitext = w['wiki'].getRawArticle(license_name)
                assert wikitext is not None, 'Could not get license article %r' % license_name
                mb.source['defaultarticlelicense'] = {
                    'name': license_name,
                    'wikitext': wikitext,
                }
        else:
            w = {
                'wiki': wiki.wiki_mwapi(baseurl, options.license, options.template_blacklist),
                'images': wiki.image_mwapi(baseurl, shared_base_url=options.shared_baseurl)
            }
            metadata = w['wiki'].getMetaData()
            mb.source = {
                'name': metadata['name'],
                'url': metadata['url'],
            }
            if 'license' in metadata:
                mb.source['defaultarticlelicense'] = metadata['license']
        
        if options.noimages:
            w['images'] = None
        else:
            if options.imagesize:
                imagesize = int(options.imagesize)
            else:
                imagesize = 800
        
        if output:
            zipfilename = output
        else:
            fd, zipfilename = tempfile.mkstemp()
            os.close(fd)
        
        if options.collectionpage:
            mwcollection = w['wiki'].getRawArticle(options.collectionpage)
            mb.loadCollectionPage(mwcollection)
        elif options.metabook:
            mb.readJsonFile(options.metabook)
        
        # do not daemonize earlier: Collection extension deletes input metabook file!
        if options.daemonize:
            daemonize()
        
        
        post_status('init')
        
        from mwlib.utils import get_multipart

        
        zf = zipfile.ZipFile(zipfilename, 'w')
        z = recorddb.ZipfileCreator(zf, w['wiki'], w['images'])
        
        post_status('parsing')
        
        mb.addArticles(articles)
        
        z.addObject('metabook.json', mb.dumpJson())
        articles = list(mb.getArticles())
        if articles:
            inc = 70./len(articles)
        else:
            inc = 0
        p = 0
        for title, revision in articles:
            post_progress(p)
            z.addArticle(title, revision=revision)        
            p += inc
        
        post_progress(70)
        
        post_status('packaging')
        
        def image_progress(i, n):
            post_progress(70 + i*(20.0/n))
        
        if not options.noimages:
            z.writeImages(size=imagesize, progress_callback=image_progress)
        
        post_progress(90)
        
        z.writeContent()
        zf.close()
        
        post_progress(95)
        
        if posturl:
            post_status('uploading')
            zf = open(zipfilename, "rb")
            ct, data = get_multipart('collection.zip', zf.read(), 'collection')
            zf.close()
            print "posting the zip to", posturl, len(data)
            req = urllib2.Request(posturl, data=data, headers={"Content-Type": ct})
            result = urllib2.urlopen(req).read()
            print "posting result was ", result

        if w['images']:
            w['images'].clear()
        
        if not output:
            os.unlink(zipfilename)
        
        post_status('finished')
        post_progress(100)
    except Exception, e:
        post_status('error')
        raise
    

def parse():
    parser = optparse.OptionParser(usage="%prog [-a|--all] --conf CONF [ARTICLE1 ...]")
    parser.add_option("-a", "--all", action="store_true", help="parse all articles")
    parser.add_option("--tb", action="store_true", help="show traceback on error")

    parser.add_option("-c", "--conf", help="config file")

    options, args = parser.parse_args()
                                   
    if not args and not options.all:
        parser.error("missing option.")
        
    if not options.conf:
        parser.error("missing --conf argument")

    articles = [unicode(x, 'utf-8') for x in args]

    conf = options.conf
    
    import traceback
    from mwlib import wiki, uparser
    
    w = wiki.makewiki(conf)
    
    db = w['wiki']

    if options.all:
        if not hasattr(db, "articles"):
            raise RuntimeError("%s does not support iterating over all articles" % (db, ))
        articles = db.articles()


    import time
    for x in articles:
        try:
            raw = db.getRawArticle(x)
            # yes, raw can be None, when we have a redirect to a non-existing article.
            if raw is None: 
                continue
            stime=time.time()
            a=uparser.parseString(x, raw=raw, wikidb=db)
        except Exception, err:
            print "F", repr(x), err
            if options.tb:
                traceback.print_exc()
        else:
            print "G", time.time()-stime, repr(x)

def serve():
    parser = optparse.OptionParser(usage="%prog --conf CONF ARTICLE [...]")
    parser.add_option("-c", "--conf", help="config file")

    options, args = parser.parse_args()
    

    conf = options.conf
    if not options.conf:
        parser.error("missing --conf argument")
    
    from mwlib import wiki, web
    
    res = wiki.makewiki(conf)
    db = res['wiki']
    images = res['images']
    from wsgiref.simple_server import make_server, WSGIServer

    from SocketServer import  ForkingMixIn
    class MyServer(ForkingMixIn, WSGIServer):
        pass

    iface, port = '0.0.0.0', 8080
    print "serving on %s:%s" % (iface, port)
    http = make_server(iface, port, web.Serve(db, res['images']), server_class=MyServer)
    http.serve_forever()
    

    
def html():
    parser = optparse.OptionParser(usage="%prog --conf CONF ARTICLE [...]")
    parser.add_option("-c", "--conf", help="config file")

    options, args = parser.parse_args()
    
    if not args:
        parser.error("missing ARTICLE argument")
        
    articles = [unicode(x, 'utf-8') for x in args]

    conf = options.conf
    if not options.conf:
        parser.error("missing --conf argument")
    
    import StringIO
    import tempfile
    import os
    import webbrowser
    from mwlib import wiki, uparser, htmlwriter
    
    res = wiki.makewiki(conf)
    db = res['wiki']
    images = res['images']

    for a in articles:
        raw=db.getRawArticle(a)
        if not raw:
            continue

        out=StringIO.StringIO()
        out.write("""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
<head>
<meta http-equiv="content-type" content="text/html; charset="utf-8"></meta>
<link rel="stylesheet" href="pedia.css" />
</head>
<body>

""")

        a=uparser.parseString(x, raw=raw, wikidb=db)
        w=htmlwriter.HTMLWriter(out, images)
        w.write(a)

        fd, htmlfile = tempfile.mkstemp(".html")
        os.close(fd)
        open(htmlfile, "wb").write(out.getvalue().encode('utf-8'))
        webbrowser.open("file://"+htmlfile)


 
def zip2odf():
    "generates odf from zipfiles"
    parser = optparse.OptionParser(usage="%prog ZIPFILE OUTPUT")
    options, args = parser.parse_args()
    
    if len(args) < 2:
        parser.error("specify ZIPFILE and OUTPUT")
    
    zipfile = args[0]
    output = args[1]
    
    from mwlib import parser, zipwiki
    from mwlib import odfwriter

    wikidb = zipwiki.Wiki(zipfile)
    imagedb = zipwiki.ImageDB(zipfile)

    
    def buildBook(wikidb):
        bookParseTree = parser.Book()
        for item in wikidb.metabook.getItems():
            if item['type'] == 'chapter':
                bookParseTree.children.append(parser.Chapter(item['title'].strip()))
            elif item['type'] == 'article':
                a = wikidb.getParsedArticle(title=item['title'], revision=item.get('revision'))
                bookParseTree.children.append(a)
        return bookParseTree

    r = odfwriter.ODFWriter(images=imagedb)    
    bookParseTree = buildBook(wikidb)
    r.writeBook(wikidb.metabook, bookParseTree, output=output)
