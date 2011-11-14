
# Copyright (c) 2007-2009 PediaPress GmbH
# See README.rst for additional licensing information.

"""main programs - installed via setuptools' entry_points"""

import optparse
import os

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
        
    from mwlib import cdbwiki

    cdbwiki.BuildWiki(input, output)()
    open(os.path.join(output, "wikiconf.txt"), "w").write("""
[wiki]
type = nucdb
path = %s
lang = en
""" % (os.path.abspath(output),))

def show():
    parser = optparse.OptionParser()
    parser.add_option("-c", "--config", help="configuration file/URL/shortcut")
    parser.add_option("-e", "--expand", action="store_true", help="expand templates")
    parser.add_option("-t", "--template", action="store_true", help="show template")
    parser.add_option("-f", help='read input from file. implies -e')
    
    options, args = parser.parse_args()
    
    if not args and not options.f:
        parser.error("missing ARTICLE argument")
        
    articles = [unicode(x, 'utf-8') for x in args]

    conf = options.config
    if not conf:
        parser.error("missing --config argument")

    from mwlib import wiki, expander
    
    db = wiki.makewiki(conf).wiki
    
    for a in articles:
        if options.template:
            defaultns=10
        else:
            defaultns=0
            
        page = db.normalize_and_get_page(a, defaultns)
        if page:
            raw = page.rawtext
        else:
            raw = None
            
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

def post():
    parser = optparse.OptionParser(usage="%prog OPTIONS")
    parser.add_option("-i", "--input", help="ZIP file to POST")
    parser.add_option('-l', '--logfile',
        help='log output to LOGFILE')
    parser.add_option("-p", "--posturl", help="HTTP POST ZIP file to POSTURL")
    parser.add_option("-g", "--getposturl",
        help='get POST URL from PediaPress.com, open upload page in webbrowser',
        action='store_true')
    options, args = parser.parse_args()
    
    use_help = 'Use --help for usage information.'
    if not options.input:
        parser.error('Specify --input.\n' + use_help)
    if (options.posturl and options.getposturl)\
        or (not options.posturl and not options.getposturl):
        parser.error('Specify either --posturl or --getposturl.\n' + use_help)
    if options.posturl:
        from mwlib.podclient import PODClient
        podclient = PODClient(options.posturl)
    elif options.getposturl:
        import webbrowser
        from mwlib.podclient import podclient_from_serviceurl
        podclient = podclient_from_serviceurl('http://pediapress.com/api/collections/')
        webbrowser.open(podclient.redirecturl)
    
    from mwlib import utils
    from mwlib.status import Status
    
    if options.logfile:
        utils.start_logging(options.logfile)

    status = Status(podclient=podclient)
    
    try:
        status(status='uploading', progress=0)
        podclient.post_zipfile(options.input)
        status(status='finished', progress=100)
    except Exception, e:
        status(status='error')
        raise


def parse():
    parser = optparse.OptionParser(usage="%prog [-a|--all] --config CONFIG [ARTICLE1 ...]")
    parser.add_option("-a", "--all", action="store_true", help="parse all articles")
    parser.add_option("--tb", action="store_true", help="show traceback on error")

    parser.add_option("-c", "--config", help="configuration file/URL/shortcut")

    options, args = parser.parse_args()
                                   
    if not args and not options.all:
        parser.error("missing option.")
        
    if not options.config:
        parser.error("missing --config argument")

    articles = [unicode(x, 'utf-8') for x in args]

    conf = options.config
    
    import traceback
    from mwlib import wiki, uparser
    
    w = wiki.makewiki(conf)
    
    db = w.wiki

    if options.all:
        if not hasattr(db, "articles"):
            raise RuntimeError("%s does not support iterating over all articles" % (db, ))
        articles = db.articles()


    import time
    for x in articles:
        try:
            page = db.normalize_and_get_page(x, 0)
            if page:
                raw = page.rawtext
            else:
                raw = None
                
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
