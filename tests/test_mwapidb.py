#! /usr/bin/env py.test
# -*- coding: utf-8 -*-

import os
import sys
import time

import py

from PIL import Image

from mwlib.mwapidb import APIHelper, ImageDB, WikiDB, MWAPIError, parse_article_url
from mwlib import parser, uparser
from mwlib.xfail import xfail

class TestAPIHelper(object):
    def test_num_tries(self):
        api_helper = APIHelper('http://localhost:12345/')
        api_helper.page_query() # ignore_errors=True per default
        py.test.raises(RuntimeError, 'api_helper.page_query(ignore_errors=False)')

class TestWikiDB(object):
    base_url = 'http://en.wikipedia.org/w/'
    
    def setup_method(self, method):
        self.w = WikiDB(self.base_url)
    
    def test_getRawArticle(self):
        raw = self.w.getRawArticle(u'Mathematics')
        assert isinstance(raw, unicode)
        assert len(raw) > 100
        
        raw2 = self.w.getRawArticle(u'Mathematics', revision='205593066')
        assert isinstance(raw2, unicode)
        assert len(raw2) > 100
        assert raw2 != raw
        
        assert None is self.w.getRawArticle('gibsjagarnich')
        assert None is self.w.getRawArticle(u'Mathematics', revision='1223423')
    
    def test_getURL(self):
        assert self.w.getURL(u'Mathematics') == '%sindex.php?title=Mathematics' % self.base_url
        assert self.w.getURL(u'Mathematics', '123') == '%sindex.php?oldid=123' % self.base_url
    
    def test_getTemplate(self):
        raw = self.w.getTemplate('Infobox')
        assert isinstance(raw, unicode)
        assert len(raw) > 10
    
    def test_getAuthors(self):
        authors = self.w.getAuthors(u'Physics')
        print 'AUTHORS:', authors
        authors = self.w.getAuthors(u'Physics', revision='206917093')
        print 'AUTHORS:', authors
        assert authors
        
        w = WikiDB('http://en.wikipedia.com/w/') # note: the .com is on purpose!
        authors = w.getAuthors(u'Physics')
        print 'AUTHORS:', authors
        assert authors

        # wikitravel.org only allows rvlimit=50 when fetching the authors:
        w = WikiDB('http://wikitravel.org/wiki/en/')
        authors = w.getAuthors(u'Egypt')
        print 'AUTHORS:', authors
        assert authors

    def test_getAuthors2(self):
        w = WikiDB('http://de.wikipedia.org/w/')
        authors = w.getAuthors(u'Glarus (Begriffsklärung)',revision='5014')
        print 'AUTHORS:', authors
        assert authors == [u'Draggi', 'ANONIPEDITS:0']

    
    def test_parse_article_url(self):
        def p(url):
            d = parse_article_url(url)
            return d['api_helper'].base_url, d['title'], d['revision']
        
        b, t, r = p('http://hu.wikipedia.org/w/index.php?title=Kanada_alkotm%C3%A1nya')
        print b, repr(t), r
        assert b == 'http://hu.wikipedia.org/w/'
        assert t == u'Kanada alkotmánya'
        
        b, t, r = p('http://hu.wikipedia.org/wiki/Kanada_alkotm%C3%A1nya')
        print b, repr(t), r
        assert b == 'http://hu.wikipedia.org/w/'
        assert t == u'Kanada alkotmánya'
        
        b, t, r = p('http://de.wikipedia.org/wiki/Hauptseite')
        assert b == 'http://de.wikipedia.org/w/'
        assert t == u'Hauptseite'
        assert r is None

        b, t, r = p('http://de.wikipedia.org/wiki/August_Ferdinand_Möbius')
        assert b == 'http://de.wikipedia.org/w/'
        assert t == u'August Ferdinand Möbius'
        assert r is None
    
        b, t, r = p('http://de.wikipedia.org/w/index.php?title=August_Ferdinand_Möbius&oldid=38212551')
        assert b == 'http://de.wikipedia.org/w/'
        assert t == u'August Ferdinand Möbius'
        assert r == 38212551
    
        b, t, r = p('http://de.wikipedia.org/w/index.php?title=August_Ferdinand_Möbius&oldid=38212551')
        assert b == 'http://de.wikipedia.org/w/'
        assert t == u'August Ferdinand Möbius'
        assert r == 38212551

        b, t, r = p('http://wikieducator.org/Otago_Polytechnic')
        assert b == 'http://wikieducator.org/'
        assert t == u'Otago Polytechnic'
        assert r is None
        
        assert parse_article_url('bla') is None
        assert parse_article_url('http://pediapress.com/') is None
        
        b, t, r = p('http://simple.pediapress.com/w/index.php/User:Jojo/Collections/test')
        assert b == 'http://simple.pediapress.com/w/'
        assert t == 'User:Jojo/Collections/test'
        assert r is None
        
        b, t, r = p('http://memory-alpha.org/en/wiki/Damar')
        assert b == 'http://memory-alpha.org/en/'
        assert t == u'Damar'
        assert r is None
        
        b, t, r = p('http://wikimediafoundation.org/wiki/Home')
        print b, t, r
        assert b == 'http://wikimediafoundation.org/w/'
        assert t == u'Home'
        assert r is None    

        b, t, r = p('http://wikitravel.org/en/Melbourne')
        print b, t, r
        assert b == 'http://wikitravel.org/wiki/en/'
        assert t == u'Melbourne'
        assert r is None
    
    def test_MW10(self):
        d = parse_article_url('http://wiki.python-ogre.org/index.php/Basic_Tutorial_1')
        w = WikiDB(api_helper=d['api_helper'])
        u = w.getURL(d['title'], revision=d['revision'])
        assert u == 'http://wiki.python-ogre.org/index.php?title=Basic_Tutorial_1'
        raw = w.getRawArticle(d['title'])
        assert len(raw) > 1000
        print 'AUTHORS:', w.getAuthors(d['title'])
    
    def test_redirect(self):
        raw = self.w.getRawArticle(u'The European Library')
        assert 'redirect' not in raw.lower()

        # with specific revision, it's a bit trickier for mwapidb:
        raw = self.w.getRawArticle(u'The European Library', revision=42994716)
        assert 'redirect' not in raw.lower()
    
    def test_getLinkURL(self):
        def make_link_node(cls, target, full_target=None):
            link = cls()
            link.target = target
            link.full_target = full_target or target
            if link.full_target[0] == ':':
                link.full_target = link.full_target[1:]
                link.colon = True
            else:
                link.colon = False
            return link
        
        u = self.w.getLinkURL(make_link_node(parser.ArticleLink, u'Philosophy'), u'Bla')
        assert u == 'http://en.wikipedia.org/w/index.php?title=Philosophy'

        u = self.w.getLinkURL(make_link_node(parser.NamespaceLink, u'Physics', u':Category:Physics'), u'Bla')
        assert u == 'http://en.wikipedia.org/w/index.php?title=Category:Physics'
        
        u = self.w.getLinkURL(make_link_node(parser.NamespaceLink, u'He!ko', u'User:He!ko'), u'Bla')
        assert u == 'http://en.wikipedia.org/w/index.php?title=User:He%21ko'
        
        u = self.w.getLinkURL(make_link_node(parser.LangLink, u'Physik', u'de:Physik'), u'Bla')
        assert u == 'http://de.wikipedia.org/wiki/Physik'
        
        u = self.w.getLinkURL(make_link_node(parser.InterwikiLink, u'Physics', u'wiktionary:Physics'), u'Bla')
        assert u == 'http://en.wiktionary.org/wiki/Physics'
    
        u = self.w.getLinkURL(make_link_node(parser.InterwikiLink, u'Physics', u'gibtsnicht:Physics'), u'Bla')
        assert u is None
        
        u = self.w.getLinkURL(make_link_node(parser.ArticleLink, u'/Bar'), u'Foo')
        assert u == 'http://en.wikipedia.org/w/index.php?title=Foo/Bar'

    @xfail
    def test_getLinkURLFail0(self):
        """http://code.pediapress.com/wiki/ticket/528"""

        r = uparser.parseString(u'', u'[[google:test]]', wikidb=self.w)
        parser.show(sys.stdout, r)
        link = r.find(parser.InterwikiLink)[0]
        print link.full_target
        assert link.full_target == 'google:test'
        assert link.target == 'test'
        assert self.w.getLinkURL(link, u'bla') == 'http://www.google.com/search?q=test'

        w = WikiDB(base_url='http://wikitravel.org/wiki/en/')
        r = uparser.parseString(u'', u'[[Dmoz:Test123]]', wikidb=w)
        link = r.find(parser.InterwikiLink)[0]
        assert link.full_target == u'Dmoz:Test123'
        assert link.url == 'http://dmoz.org/Regional/Test123'

    @xfail
    def test_getLinkURLFail1(self):
        """http://code.pediapress.com/wiki/ticket/528"""

        r = uparser.parseString(u'', u'[[fr:test]]', wikidb=self.w)
        parser.show(sys.stdout, r)
        link = r.find(parser.LangLink)[0]
        print link.full_target
        assert link.full_target == 'fr:test'
        assert link.target == 'test'
        assert self.w.getLinkURL(link, u'bla') == 'http://fr.wikipedia.org/wiki/test'

    @xfail
    def test_getLinkURLFail2(self):
        """http://code.pediapress.com/wiki/ticket/537"""

        r = uparser.parseString(u'', u'[[Wikipedia:test]]', wikidb=self.w)
        parser.show(sys.stdout, r)
        link = r.find(parser.NamespaceLink)[0]
        print link.full_target
        assert link.full_target == 'Wikipedia:test'
        assert link.target == 'test'
        assert self.w.getLinkURL(link, u'bla') == 'http://en.wikipedia.org/w/index.php?title=Wikipedia:test'

    @xfail
    def test_getLinkURLFail3(self):
        """http://code.pediapress.com/wiki/ticket/537"""

        w = WikiDB(base_url='http://memory-alpha.org/en/')
        r = uparser.parseString(u'', u'[[3dgame:Test123]]', wikidb=w)
        link = r.find(parser.InterwikiLink)[0]
        assert link.full_target == u'3dgame:Test123'
        assert link.url == 'http://3dgame.wikia.com/wiki/Test123'

        # Wikia doesn't set the language attribute in interwikimap entries for lang links
        w = WikiDB(base_url='http://memory-alpha.org/en/')
        r = uparser.parseString(u'', u'[[es:español]]', wikidb=w)
        link = r.find(parser.LangLink)[0]
        assert link.full_target == u'es:español'
        assert link.url == 'http://memory-alpha.org/es/wiki/espa%C3%B1ol'

    def test_invalid_base_url(self):
        print py.test.raises(MWAPIError, WikiDB, 'http://pediapress.com/')
    
    def test_template_exclusion_category(self):
        w = WikiDB(
            base_url='http://simple.pediapress.com/w/',
            template_exclusion_category=u'Exclude in print',
        )
        assert w.getTemplate('Excluded') is None
        assert w.getTemplate('colours') is not None

        w = WikiDB(
            base_url='http://simple.pediapress.com/w/',
        )
        w.setTemplateExclusion(category=u'Exclude in print')
        assert w.getTemplate('Excluded') is None
        assert w.getTemplate('colours') is not None

    def test_unicodeInPrintTemplate(self):
        w = WikiDB(
            base_url='http://simple.pediapress.com/w/',
        )
        w.setTemplateExclusion(pattern=u'Vom Druck ausschließen')
        assert w.getTemplate(u'blaß') is None
    
    def test_byte_order_mark(self):
        ah = APIHelper('http://www.wereldpagina.nl')
        assert ah.is_usable()

    def test_getSource(self):
        src = self.w.getSource(u'Main Page')
        assert src
        interwikimap = src['interwikimap']
        assert interwikimap
        assert isinstance(interwikimap, dict)
        loc = src['locals']
        assert loc
        assert isinstance(loc, unicode)

    

class TestImageDB(object):
    base_url = 'http://en.wikipedia.org/w/'
    
    existing_image_name = u'Serra de Cals.jpg'
    existing_image_url = 'http://upload.wikimedia.org/wikipedia/commons/6/6b/Serra_de_Cals.jpg'
    nonexisting_image_name = u'Test12123213.jpg'
    
    def setup_method(self, method):
        self.imagedb = ImageDB(self.base_url)
    
    def teardown_method(self, method):
        self.imagedb.clear()
    
    def check(self, size, success):
        if success:
            name = self.existing_image_name
            if size is None:
                check_url = self.existing_image_url
            else:
                check_url = 'http://upload.wikimedia.org/wikipedia/commons/thumb/6/6b/Serra_de_Cals.jpg/%spx-Serra_de_Cals.jpg' % size
        else:
            name = self.nonexisting_image_name
            check_url = None
        
        time.sleep(0.5)
        p = self.imagedb.getDiskPath(name, size=size)
        assert self.imagedb.getURL(name, size=size) == check_url
        if success:
            assert os.path.exists(p)
        else:
            assert p is None
    
    def test_succeed_gen(self):
        for size in (None, 100):
            yield self.check, size, True
    
    def test_fail_get(self):
        for size in (None, 100):
            yield self.check, size, False
    
    def test_spaces_in_imagename(self):
        name = u'DNA As Structure Formula (German).PNG'
        size = 100
        p = self.imagedb.getDiskPath(name, size=size)
        assert p is not None
    
    def test_unicode_imagename(self):
        name = u'Balneario_Iporá_lago_02.jpg'
        size = 100
        p = self.imagedb.getDiskPath(name, size=size)
        assert p is not None
    
    def test_resize(self):
        big_size = 2000
        
        p = self.imagedb.getDiskPath(self.existing_image_name)
        img = Image.open(p)
        orig_size = img.size
        print 'ORIG', orig_size
        assert orig_size[0] < big_size
        assert orig_size[1] < big_size
        
        p = self.imagedb.getDiskPath(self.existing_image_name, size=100)
        img = Image.open(p)
        print 'CONVERTED1', img.size
        assert img.size[0] == 100
        assert img.size[1] < 100
        
        p = self.imagedb.getDiskPath(self.existing_image_name, size=big_size)
        img = Image.open(p)
        print 'CONVERTED2', img.size
        assert img.size == orig_size
    
    def test_getImageTemplates(self):
        templates = self.imagedb.getImageTemplates(self.existing_image_name)
        assert templates
    
    def test_svg(self):
        url = self.imagedb.getURL(u'Flag of the United States.svg', size=800)
        assert not url.endswith('.svg')
    
    def test_non_full_url(self):
        """WikiEducator (any probably many other MediaWikis) return image URLs
        that do not start with http://hostname.
        """
        
        imgdb = ImageDB('http://wikieducator.org/')
        t = u'Mediawiki_logo_m.png'
        assert imgdb.getURL(t).startswith('http://')
        imgdb.getDiskPath(t)
    
    def test_getDescriptionURL(self):
        imgdb = ImageDB('http://en.wikipedia.org/w/')
        t = u'Sertraline-A-3D-balls.png'
        du = imgdb.getDescriptionURL(t)
        assert du == 'http://commons.wikimedia.org/wiki/Image:Sertraline-A-3D-balls.png'
    
        imgdb = ImageDB('http://memory-alpha.org/en/')
        t = u'Damar2375.jpg'
        du = imgdb.getDescriptionURL(t)
        print du
        assert du == 'http://memory-alpha.org/en/wiki/Image:Damar2375.jpg'
    
    def test_getPath(self):
        p = self.imagedb.getPath(u'Flag of the United States.svg')
        assert p == 'commons/a/a4/Flag_of_the_United_States.svg'
        p = self.imagedb.getPath(u'Flag of the United States.svg', size=800)
        assert p == 'thumb/a/a4/Flag_of_the_United_States.svg/800px-Flag_of_the_United_States.svg.png'
    
    def test_getContributors(self):
        # test uniqueness
        c = self.imagedb.getContributors(u'Flag of France.svg')
        print c
        assert c
        assert len(set(c)) == len(c)

        # image contains User: link in Information tempalte:
        c = self.imagedb.getContributors(u'Hong Kong Skyline Restitch - Dec 2007.jpg')
        print c
        assert c
        
        # image contains plain username in Information template:
        c = self.imagedb.getContributors(u'Barakhambaroad.jpg')
        print c
        assert c
        
        c = self.imagedb.getContributors(u'Uroplatus_Sikorae_Analamazaotra_Forest_Madagascar.jpg')
        print c
        assert c
        
        c = self.imagedb.getContributors(u'OlympeDeGouge.jpg')
        print c
        assert c

        # Author field in Information template contains lots of text and a NamedURL
        c = self.imagedb.getContributors(u'Flag of Spain.svg')
        print c
        assert c

        # Author field in Information template contains [:de:User:...] link and other text
        c = self.imagedb.getContributors(u'Augustinerkirche Mainz innen.jpg')
        print c
        assert c

        c = self.imagedb.getContributors(u'Flag of Israel.svg')
        print c
        assert c

        
        
    

