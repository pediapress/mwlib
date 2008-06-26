
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
    from mwlib.options import OptionParser

    parser = OptionParser()
    parser.add_option("-o", "--output", help="write output to OUTPUT")
    parser.add_option("-p", "--posturl", help="http post to POSTURL (directly)")
    parser.add_option("-g", "--getposturl",
                      help='get POST URL from PediaPress.com and open upload page in webbrowser',
                      action='store_true')
    parser.add_option("-i", "--imagesize",
                      help="max. pixel size (width or height) for images (default: 800)",
                      default=800)
    parser.add_option("-d", "--daemonize", action="store_true",
                      help='become a daemon process as soon as possible')
    options, args = parser.parse_args()
    
    use_help = 'Use --help for usage information.'
    if options.posturl and options.getposturl:
        parser.error('Please specify either --posturl or --getposturl, not both.\n' + use_help)
    if not options.posturl and not options.getposturl and not options.output:
        parser.error('Neither --output, nor --posturl or --getposturl specified. This would result in a no-op...')
    
    try:
        options.imagesize = int(options.imagesize)
        assert options.imagesize > 0
    except (ValueError, AssertionError):
        parser.error('Argument for --imagesize must be an integer > 0.')
    
    import os
    import tempfile
    import zipfile
    
    if options.posturl:
        from mwlib.podclient import PODClient
        podclient = PODClient(options.posturl)
    elif options.getposturl:
        import webbrowser
        from mwlib.podclient import podclient_from_serviceurl
        podclient = podclient_from_serviceurl('http://pediapress.com/api/collections/')
        webbrowser.open(podclient.redirecturl)
    else:
        podclient = None
    
    delete_files = []
    
    if options.daemonize:
        from mwlib.utils import daemonize
        if options.metabook:
            import shutil
            fd, tmp = tempfile.mkstemp()
            os.close(fd)
            shutil.copyfile(options.metabook, tmp)
            options.metabook = tmp
            delete_files.append(tmp)
        daemonize()
    
    def set_status(status):
        print 'Status: %s' % status
        if podclient is not None:
            podclient.post_status(status)
        
    def set_progress(progress):
        print 'Progress: %d%%' % progress
        if podclient is not None:
            podclient.post_progress(progress)
    
    def set_current_article(title):
        print 'Current Article: %r' % title
        if podclient is not None:
            podclient.post_current_article(title)

    # try:... except:... finally:... does not work in python 2.4
    # use atexit instead
    def cleanup():
        for path in delete_files:
            try:
                os.unlink(path)
            except Exception, e:
                print 'Could not delete file %r: %s' % (path, e)
                
    import atexit
    atexit.register(cleanup)
        
    try:
        set_status('init')
        
        from mwlib import recorddb, metabook, mwapidb
        
        env = parser.env
        
        if options.output is None:
            fd, options.output = tempfile.mkstemp()
            os.close(fd)
            delete_files.append(options.output)
        zf = zipfile.ZipFile(options.output, 'w')
        z = recorddb.ZipfileCreator(zf, imagesize=options.imagesize)
        
        set_status('parsing')
        articles = list(parser.metabook.getArticles())
        if articles:
            inc = 90./len(articles)
        else:
            inc = 0
        p = 0
        for item in articles:
            set_progress(p)
            d = mwapidb.parse_article_url(item['title'].encode('utf-8'))
            if d is not None:
                item['title'] = d['title']
                item['revision'] = d['revision']
                wikidb = mwapidb.WikiDB(api_helper=d['api_helper'])
                imagedb = mwapidb.ImageDB(api_helper=d['api_helper'])
            else:
                wikidb = env.wiki
                imagedb = env.images
            set_current_article(item['title'])
            z.addArticle(item['title'], revision=item.get('revision', None), wikidb=wikidb, imagedb=imagedb)
            
            p += inc
        set_progress(90)
        
        for license in env.get_licenses():
            z.parseArticle(
                title=license['title'],
                raw=license['wikitext'],
                wikidb=env.wiki,
                imagedb=env.images,
            )
        
        z.addObject('metabook.json', parser.metabook.dumpJson())
        
        z.writeContent()
        zf.close()
        set_progress(95)
        
        if podclient:
            podclient.post_zipfile(options.output)
        
        if env.images:
            env.images.clear()
        
        set_status('finished')
        set_progress(100)
    except Exception, e:
        set_status('error')
        raise

def render():
    from mwlib.options import OptionParser
    
    parser = OptionParser(conf_optional=True)
    parser.add_option("-o", "--output", help="write output to OUTPUT")
    parser.add_option("-w", "--writer", help='use writer backend WRITER')
    parser.add_option("-W", "--writer-options", help='";"-separated list of additional writer-specific options')
    parser.add_option("-e", "--error-file", help='write errors to this file')
    parser.add_option("-s", "--status-file", help='write status/progress info to this file')
    parser.add_option("--list-writers", action='store_true', help='list available writers and exit')
    parser.add_option("-d", "--daemonize", action="store_true",
                      help='become a daemon process as soon as possible')
    options, args = parser.parse_args()
    
    import simplejson
    import sys
    import traceback
    import pkg_resources
    from mwlib.writerbase import WriterError
    
    use_help = 'Use --help for usage information.'
    
    if options.list_writers:
        for entry_point in pkg_resources.iter_entry_points('mwlib.writers'):
            try:
                writer = entry_point.load()
                if hasattr(writer, 'description'):
                    description = writer.description
                else:
                    description = '<no description>'
            except Exception, e:
                description = '<NOT LOADABLE: %s>' % e
            print '%s\t%s' % (entry_point.name, description)
        return
    
    if options.output is None:
        parser.error('Please specify an output file with --output.\n' + use_help)
    
    if options.writer is None:
        parser.error('Please specify a writer with --writer.\n' + use_help)    
    try:
        entry_point = pkg_resources.iter_entry_points('mwlib.writers', options.writer).next()
    except StopIteration:
        sys.exit('No such writer: %r (use --list-writers to list available writers)' % options.writer)
    try:
        writer = entry_point.load()
    except Exception, e:
        sys.exit('Could not load writer %r: %s' % (options.writer, e))
    
    writer_options = {}
    if options.writer_options:
        for wopt in options.writer_options.split(';'):
            if '=' in wopt:
                key, value = wopt.split('=', 1)
                writer_options[key] = value
            else:
                writer_options[wopt] = True
    
    if options.daemonize:
        from mwlib.utils import daemonize
        daemonize()
    
    last_status = {}
    def set_status(status=None, progress=None, article=None):
        if status is not None:
            last_status['status'] = status
            print 'STATUS: %s' % status
        if progress is not None:
            assert 0 <= progress and progress <= 100, 'status not in range 0..100'
            last_status['progress'] = progress
            print 'PROGRESS: %d%%' % progress
        if article is not None:
            last_status['article'] = article
            print 'ARTICLE: %r' % article
        if options.status_file:
            open(options.status_file, 'wb').write(simplejson.dumps(last_status).encode('utf-8'))
    
    try:
        set_status(status='init', progress=0)
        writer(parser.env, output=options.output, status_callback=set_status, **writer_options)
        set_status(status='finished', progress=100)
    except WriterError, e:
        set_status(status='error')
        if options.error_file:
            open(options.error_file, 'wb').write(str(e))
        raise
    except Exception, e:
        set_status(status='error')
        if options.error_file:
            traceback.print_exc(file=open(options.error_file, 'wb'))
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
