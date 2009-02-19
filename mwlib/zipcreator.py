#! /usr/bin/env python

# Copyright (c) 2007-2009 PediaPress GmbH
# See README.txt for additional licensing information.

import os
import re
import tempfile
import threading
import zipfile
try:
    import json
except ImportError:
    import simplejson as json

from mwlib import expander, jobsched, metabook, mwapidb, parser, uparser, utils
from mwlib.recorddb import RecordDB
import mwlib.log

# ==============================================================================

log = mwlib.log.Log("zipcreator")

# ==============================================================================


class ZipCreator(object):
    """Create ZIP files usable as WikiDB
    
    See docs/zipfile.txt
    """
    
    redirect_rex = re.compile(r'^#redirect:?\s*?\[\[(?P<redirect>.*?)\]\]', re.IGNORECASE)
    
    def __init__(self, zf,
        imagesize=None,
        num_threads=10,
        status=None,
        num_articles=None,
    ):
        """
        @param zf: ZipFile object
        @type zf: L{zipfile.ZipFile}
        
        @param imagesize: max. size of images
        @type imagesize: int
        
        @param num_threads: number of threads for parallel fetchgin
            (set to 0 to turn threading off)
        @type num_threads: int
        """
        
        self.zf = zf
        self.imagesize = imagesize
        self.status = status
        self.articles = {}
        self.templates = {}
        self.sources = {}
        self.images = {}
        self.node_stats = {} 
        self.num_articles = num_articles
        self.article_count = 0
        self.image_infos = set()    
        self.zf_lock = threading.RLock()
        if num_threads > 0:
            self.jobsched = jobsched.JobScheduler(num_threads)
        else:
            self.jobsched = jobsched.DummyJobScheduler()
        self.article_jobs = []
    
    def addObject(self, name, value):
        """Add a file with name and contents value to the ZIP file
        
        @param name: name for entry in ZIP file, will be UTF-8 encoded
        @type name: unicode
        
        @param value: content for ZIP file entry
        @type value: str
        """
        
        self.zf_lock.acquire()
        try:
            self.zf.writestr(name.encode('utf-8'), value)
        finally:
            self.zf_lock.release()
    
    def addArticle(self, title,
        revision=None,
        wikidb=None,
        imagedb=None,
    ):
        """Add article with given title and revision to ZIP file. This will add
        all referenced templates and images, too.
        
        @param title: article title
        @type title: unicode
        
        @param revision: article revision (optional)
        @type revision: int
        
        @param wikidb: WikiDB to use
        
        @param imagedb: ImageDB to use (optional)
        """
        
        self.article_jobs.append({
            'title': title,
            'revision': revision,
            'wikidb': wikidb,
            'imagedb': imagedb,
        })
    
    def parseArticle(self, title,
        revision=None,
        raw=None,
        wikidb=None,
        imagedb=None,
    ):
        """Parse article with given title, revision and raw wikitext, adding all
        referenced templates and images, but not adding the article itself.
        
        @param title: title of article
        @type title: unicode
        
        @param revision: revision of article (optional)
        @type revision: int
        
        @param raw: wikitext of article
        @type raw: unicode
        
        @param wikidb: WikiDB to use
        
        @param imagedb: ImageDB to use (optional)
        """
        
        recorddb = RecordDB(wikidb, self.articles, self.templates, self.sources)
        parse_tree = uparser.parseString(title,
            revision=revision,
            raw=raw,
            wikidb=recorddb,
        )
        if imagedb is None:
            return

        stats = self.node_stats
        for node in parse_tree.allchildren():
            if isinstance(node, parser.ImageLink):
                self.image_infos.add((node.target, imagedb, wikidb))
            elif isinstance(node, parser.TagNode) and node.caption == 'imagemap':
                imagemap = getattr(node, 'imagemap', None)
                if imagemap is not None:
                    imagelink = getattr(imagemap, 'imagelink', None)
                    if imagelink is not None:
                        self.image_infos.add((imagelink.target, imagedb, wikidb))
            # stats
            k, w  = utils.get_nodeweight(node)
            stats[k] = stats.get(k, 0) + w


    
    def join(self):
        """Finish ZIP file by writing the actual content"""
        
        if self.status:
            self.status(status=u'fetching articles')
            self.fetcharticle_status = self.status.getSubRange(0, 20)
            self.fetchtemplate_status = self.status.getSubRange(21, 40)
            self.parse_status = self.status.getSubRange(41, 60)
            self.fetchimages_status = self.status.getSubRange(61, 100)
        else:
            self.fetcharticle_status = self.fetchtemplate_status = self.parse_status = self.fetchimages_status = None
        for info in self.article_jobs:
            self.fetchArticle(
                title=info['title'],
                revision=info['revision'],
                wikidb=info['wikidb'],
            )
        self.jobsched.join()
        if self.status:
            self.status(status=u'fetching templates', article='')
        templates = set()
        for info in self.article_jobs:
            try:
                raw = self.articles[info['title']]['content']
            except KeyError:
                continue

            for name in expander.get_templates(raw, info['title']):
                templates.add((name, info['wikidb']))
                            
        self.num_templates = len(templates)
        self.template_count = 0 
        for title, wikidb in templates:
            self.fetchTemplate(title, wikidb)
        self.jobsched.join()
        
        if self.status:
            self.status(status=u'parsing articles')
        n = len(self.article_jobs)
        for i, info in enumerate(self.article_jobs):
            try:
                raw = self.articles[info['title']]['content']
            except KeyError:
                continue
            if self.parse_status:
                self.parse_status(article=info['title'])
            self.parseArticle(
                title=info['title'],
                revision=info['revision'],
                raw=raw,
                wikidb=info['wikidb'],
                imagedb=info['imagedb'],
            )
            if self.parse_status:
                self.parse_status(progress=i*100/n)
        if self.status:
            self.status(status=u'fetching images', article='')
        self.num_images = len(self.image_infos)
        self.image_count = 0
        for i in self.image_infos:
            self.addImage(*i)
        self.jobsched.join()
      
        self.addObject('content.json', json.dumps(dict(
            articles=self.articles,
            templates=self.templates,
            sources=self.sources,
            images=self.images,
        )))
    
    def fetchArticle(self, title, revision, wikidb):
        def fetch_article_job(job_id):
            if self.fetcharticle_status:
                self.fetcharticle_status(article=title)
            recorddb = RecordDB(wikidb, self.articles, self.templates, self.sources)
            raw = recorddb.getRawArticle(title, revision=revision)
            if raw is None:
                log.warn('Could not get article %r' % title)
            else:
                mo = self.redirect_rex.search(raw)
                if mo:
                    raw = recorddb.getRawArticle(mo.group('redirect'))
                    if raw is None:
                        log.warn('Could not get redirected article %r (from %r)' % (
                            mo.group('redirect'), title
                        ))
            self.article_count += 1
            if self.fetcharticle_status:
                self.fetcharticle_status(progress=self.article_count*100/self.num_articles)
        
        self.jobsched.add_job(title, fetch_article_job) # FIXME: title is not unique
    
    def fetchTemplate(self, name, wikidb):
        def get_template_job(name):
            recorddb = RecordDB(wikidb, self.articles, self.templates, self.sources)
            try:
                recorddb.getTemplate(name)
            finally:
                self.template_count += 1
                if self.fetchtemplate_status:
                    self.fetchtemplate_status(progress=self.template_count*100/self.num_templates)
        
        self.jobsched.add_job(name, get_template_job)
    
    def addImage(self, name, imagedb=None, wikidb=None):
        """Add image with given name to the ZIP file
        
        @param name: image name
        @type name: uncidoe
        
        @param imagedb: ImageDB to use
        """
        
        if name in self.images:
            return
        self.images[name] = {}
        
        def fetch_image_job(name):
            path = imagedb.getDiskPath(name, size=self.imagesize)
            if path is None:
                log.warn('Could not get image %r' % name)
                return
            self.zf_lock.acquire()
            try:
                zipname = u"images/%s" % name.replace("'", '-')
                self.zf.write(path, zipname.encode("utf-8"))
            finally:
                self.zf_lock.release()
            self.images[name]['url'] = imagedb.getURL(name, size=self.imagesize)
            descriptionurl = imagedb.getDescriptionURL(name)
            if descriptionurl:
                self.images[name]['descriptionurl'] = descriptionurl
            templates = imagedb.getImageTemplates(name, wikidb=wikidb)
            if templates:
                self.images[name]['templates'] = templates
            if hasattr(imagedb, 'getContributors'):
                contribs = imagedb.getContributors(name, wikidb=wikidb)
                if contribs:
                    self.images[name]['contributors'] = contribs
            if self.fetchimages_status:
                self.image_count += 1
                self.fetchimages_status(progress=self.image_count*100/self.num_images)
        
        self.jobsched.add_job(name, fetch_image_job)

    def check(self, articles):
        for item in articles:
            try:
                article = self.articles[item['title']]
            except KeyError:
                raise RuntimeError('Could not fetch article %r' % item['title'])
            if not article.get('url'):
                raise RuntimeError('Have no URL for article %r' % item['title'])
            if not article.get('source-url'):
                raise RuntimeError('Have not source URL for article %r' % item['title'])
            if not article.get('content'):
                raise RuntimeError('Have empty content for article %r' % item['title'])
            if not article['source-url'] in self.sources:
                raise RuntimeError('Unknown source URL %r for article %r' % (
                    article['source-url'], item['title']),
                )
    

# ==============================================================================

def make_zip_file(output, env,
    status=None,
    num_threads=10,
    imagesize=800,
):
    if output is None:
        fd, output = tempfile.mkstemp(suffix='.zip')
        os.close(fd)
    
    fd, tmpzip = tempfile.mkstemp(suffix='.zip', dir=os.path.dirname(output))
    os.close(fd)
    zf = zipfile.ZipFile(tmpzip, 'w')
    
    try:
        articles = metabook.get_item_list(env.metabook, filter_type='article')
        
        z = ZipCreator(zf,
            imagesize=imagesize,
            num_threads=num_threads,
            status=status,
            num_articles=len(articles),
        )
        
        for item in articles:
            d = mwapidb.parse_article_url(item['title'].encode('utf-8'))
            if d is not None:
                item['title'] = d['title']
                item['revision'] = d['revision']
                wikidb = mwapidb.WikiDB(api_helper=d['api_helper'])
                imagedb = mwapidb.ImageDB(api_helper=d['api_helper'])
            else:
                wikidb = env.wiki
                imagedb = env.images
            z.addArticle(item['title'],
                revision=item.get('revision', None),
                wikidb=wikidb,
                imagedb=imagedb,
            )
        
        for license in env.get_licenses():
            z.parseArticle(
                title=license['title'],
                raw=license['wikitext'],
                wikidb=env.wiki,
                imagedb=env.images,
            )
        
        z.join()
        
        # using check() is a bit rigorous: sometimes articles just cannot be
        # fetched -- PDFs should be generated nevertheless
        #z.check(articles)

        z.addObject('metabook.json', json.dumps(env.metabook))

        # add stats for later analysis
        z.node_stats["Chapter"] = len(metabook.get_item_list(env.metabook, filter_type='chapter'))
        z.addObject('node_stats.json', json.dumps(z.node_stats)) 

        zf.close()
        if os.path.exists(output): # Windows...
            os.unlink(output)
        os.rename(tmpzip, output)
    
        if env.images and hasattr(env.images, 'clear'):
            env.images.clear()
    
        if status is not None:
            status(progress=100)
        return output
    finally:
        if os.path.exists(tmpzip):
            utils.safe_unlink(tmpzip)
