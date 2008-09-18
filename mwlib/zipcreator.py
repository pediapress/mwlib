#! /usr/bin/env python

# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.

import os
import re
import simplejson
import tempfile
import threading
import zipfile

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
    
    def __init__(self, zf, imagesize=None, status=None, num_articles=None):
        """
        @param zf: ZipFile object
        @type zf: L{zipfile.ZipFile}
        
        @param imagesize: max. size of images
        @type imagesize: int
        """
        
        self.zf = zf
        self.imagesize = imagesize
        self._status = status
        self.num_articles = num_articles
        self.articles = {}
        self.templates = {}
        self.sources = {}
        self.images = {}
        self.article_count = 0
    
    def status(self, **kwargs):
        if self._status is not None:
            self._status(**kwargs)
    
    def addObject(self, name, value):
        """Add a file with name and contents value to the ZIP file
        
        @param name: name for entry in ZIP file, will be UTF-8 encoded
        @type name: unicode
        
        @param value: content for ZIP file entry
        @type value: str
        """
        
        self.zf.writestr(name.encode('utf-8'), value)
    
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
        
        if title in self.articles:
            return
        self.articles[title] = {}
        
        self.status(article=title)
        
        recorddb = RecordDB(wikidb, self.articles, self.templates, self.sources)
        raw = recorddb.getRawArticle(title, revision=revision)
        if raw is None:
            log.warn('Could not get article %r' % title)
            return
        mo = self.redirect_rex.search(raw)
        if mo:
            raw = recorddb.getRawArticle(mo.group('redirect'))
            if raw is None:
                log.warn('Could not get redirected article %r (from %r)' % (
                    mo.group('redirect'), title
                ))
                return
        self.parseArticle(title,
            revision=revision,
            raw=raw,
            wikidb=wikidb,
            imagedb=imagedb,
        )
        self.article_count += 1
        if self.num_articles:
            self.status(progress=self.article_count*100//self.num_articles)
    
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
        for node in parse_tree.allchildren():
            if isinstance(node, parser.ImageLink):
                self.addImage(node.target, imagedb=imagedb, wikidb=wikidb)
            elif isinstance(node, parser.TagNode) and node.caption == 'imagemap':
                imagemap = getattr(node, 'imagemap', None)
                if imagemap is not None:
                    imagelink = getattr(imagemap, 'imagelink', None)
                    if imagelink is not None:
                        self.addImage(imagelink.target, imagedb=imagedb, wikidb=wikidb)

    
    def addImage(self, name, imagedb=None, wikidb=None):
        """Add image with given name to the ZIP file
        
        @param name: image name
        @type name: unicode
        
        @param imagedb: ImageDB to use
        """
        
        if name in self.images:
            return
        self.images[name] = {}
        
        path = imagedb.getDiskPath(name, size=self.imagesize)
        if path is None:
            log.warn('Could not get image %r' % name)
            return
        zipname = u"images/%s" % name.replace("'", '-')
        self.zf.write(path, zipname.encode("utf-8"))
        self.images[name]['url'] = imagedb.getURL(name, size=self.imagesize)
        descriptionurl = imagedb.getDescriptionURL(name)
        if descriptionurl:
            self.images[name]['descriptionurl'] = descriptionurl
        templates = imagedb.getImageTemplates(name, wikidb=wikidb)
        if templates:
            self.images[name]['templates'] = templates
    
    def join(self):
        """Finish ZIP file by writing the actual content"""
        
        self.addObject('content.json', simplejson.dumps(dict(
            articles=self.articles,
            templates=self.templates,
            sources=self.sources,
            images=self.images,
        )))
    

# ==============================================================================


class ThreadedZipCreator(ZipCreator):
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
        
        super(ThreadedZipCreator, self).__init__(zf,
            imagesize=imagesize,
            status=status,
            num_articles=num_articles,
        )
        self.zf_lock = threading.RLock()
        if num_threads > 0:
            self.jobsched = jobsched.JobScheduler(num_threads)
        else:
            self.jobsched = jobsched.DummyScheduler()
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
            super(ThreadedZipCreator, self).addObject(name, value)
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
    
    def join(self):
        """Finish ZIP file by writing the actual content"""
        
        self.status(status=u'fetching articles')
        for info in self.article_jobs:
            self.fetchArticle(
                title=info['title'],
                revision=info['revision'],
                wikidb=info['wikidb'],
            )
        self.jobsched.join()
        self.status(progress=33)
        
        self.status(status=u'fetching templates')
        templates = set()
        for info in self.article_jobs:
            try:
                raw = self.articles[info['title']]['content']
            except KeyError:
                continue
            parser = expander.Parser(raw)
            for template in parser.parse().find(expander.Template):
                # FIXME: filter out magics
                try:
                    name = template.children[0].children[0]
                except IndexError:
                    continue
                templates.add((name, info['wikidb']))
        for title, wikidb in templates:
            self.fetchTemplate(title, wikidb)
        self.jobsched.join()
        self.status(progress=50)
        
        self.status(status=u'fetching images')
        for info in self.article_jobs:
            try:
                raw = self.articles[info['title']]['content']
            except KeyError:
                continue
            self.parseArticle(
                title=info['title'],
                revision=info['revision'],
                raw=raw,
                wikidb=info['wikidb'],
                imagedb=info['imagedb'],
            )
        self.jobsched.join()
        
        self.addObject('content.json', simplejson.dumps(dict(
            articles=self.articles,
            templates=self.templates,
            sources=self.sources,
            images=self.images,
        )))
    
    def fetchArticle(self, title, revision, wikidb):
        def fetch_article_job(job_id):
            recorddb = RecordDB(wikidb, self.articles, self.templates, self.sources)
            raw = recorddb.getRawArticle(title, revision=revision)
            if raw is None:
                log.warn('Could not get article %r' % title)
                return
            mo = self.redirect_rex.search(raw)
            if mo:
                raw = recorddb.getRawArticle(mo.group('redirect'))
                if raw is None:
                    log.warn('Could not get redirected article %r (from %r)' % (
                        mo.group('redirect'), title
                    ))
                    return
        
        self.jobsched.add_job(title, fetch_article_job) # FIXME: title is not unique
    
    def fetchTemplate(self, name, wikidb):
        def get_template_job(name):
            recorddb = RecordDB(wikidb, self.articles, self.templates, self.sources)
            recorddb.getTemplate(name)
        
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
        
        self.jobsched.add_job(name, fetch_image_job)
    

# ==============================================================================

def make_zip_file(output, env,
    status=None,
    num_threads=10,
    imagesize=800,
):
    if status is None:
        status = lambda **kwargs: None
    
    if output is None:
        fd, output = tempfile.mkstemp(suffix='.zip')
        os.close(fd)
    
    fd, tmpzip = tempfile.mkstemp(suffix='.zip', dir=os.path.dirname(output))
    os.close(fd)
    zf = zipfile.ZipFile(tmpzip, 'w')
    
    try:
        articles = metabook.get_item_list(env.metabook, filter_type='article')
        
        if num_threads > 0:
            z = ThreadedZipCreator(zf,
                imagesize=imagesize,
                num_threads=num_threads,
                status=status,
                num_articles=len(articles),
            )
        else:
            z = ZipCreator(zf,
                imagesize=imagesize,
                status=status,
                num_articles=len(articles),
            )
        
        # if articles:
        #     class IncProgress(object):
        #         inc = 100./len(articles)
        #         p = 0
        #         def __call__(self, title):
        #             self.p += self.inc
        #             status(progress=int(self.p), article=title)
        #     inc_progress = IncProgress()
        # else:
        #     inc_progress = None
        
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
        z.addObject('metabook.json', simplejson.dumps(env.metabook))
        zf.close()
        if os.path.exists(output): # Windows...
            os.unlink(output)
        os.rename(tmpzip, output)
    
        if env.images and hasattr(env.images, 'clear'):
            env.images.clear()
    
        status(progress=100)
        return output
    finally:
        if os.path.exists(tmpzip):
            utils.safe_unlink(tmpzip)
