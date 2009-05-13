#! /usr/bin/env python

# Copyright (c) 2007-2009 PediaPress GmbH
# See README.txt for additional licensing information.

import re

class inspect_authors(object):
    ip_rex = re.compile(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$')
    bot_rex = re.compile(r'bot', re.IGNORECASE)
    redirect_rex = re.compile(r'^#redirect:?\s*?\[\[.*?\]\]', re.IGNORECASE)

    def get_authors(self, revs):
        """Return names of non-bot, non-anon users for
        non-minor changes of given article (before given revision).

        The data that can be used to to compute a list of authors is limited:
        http://de.wikipedia.org/w/api.php?action=query&prop=revisions&rvlimit=500&
        rvprop=ids|timestamp|flags|comment|user|size&titles=Claude_Bourgelat

        Authors are sorted by the approximate size of their contribution.

        Edits are considered to be reverts if two edits end up in the sames size within 
        N edits and have the reverting edit has the revid of the reverted edit in its commet.

        @returns: sorted list of principal authors
        @rtype: list([unicode])
        """

        if not revs:
            return []

        REVERT_LOOKBACK = 5 # number of revisions to check for same size (assuming a revert)
        USE_DIFF_SIZE = False # whether to sort by diffsize or by alphabet
        FILTER_REVERTS = False # can not be used if 
        def filter_reverts(revs):
            # Start with oldest edit:
            # (note that we can *not* just pass rvdir=newer to API, because if we
            # have a given article revision, we have to get revisions older than
            # that)
            
            
            revs.reverse() 
            # remove revs w/o size (happens with move)
            revs = [r for r in revs if "size" in r]
            for i, r in enumerate(revs):
                if "reverted" in r or i==0:
                    continue
                last_size = revs[i-1]['size']
                for j in range(i+1,min(len(revs)-1, i+REVERT_LOOKBACK+1)):
                    if revs[j]['size'] == last_size and str(r['revid']) in revs[j].get('comment',''): 
                        for jj in range(i,j+1): # skip the reverted, all in between, and the reverting edit 
                            revs[jj]['reverted'] = True 
                        break
            #print "reverted", [r for r in revs if "reverted" in r]
            return [r for r in revs if not "reverted" in r]


        def mycmp(r1, r2):
            return cmp(r1.get("revid"), r2.get("revid"))
            
        revs.sort(cmp=mycmp)

        if FILTER_REVERTS:
            revs = list(filter_reverts(revs))

        # calc an approximate size for each edit (true if author only *added* to the article)
        if USE_DIFF_SIZE:
            for i, r in enumerate(revs):
                if i == 0:
                    r['diff_size'] = r['size']
                else:
                    r['diff_size'] = abs(r['size']-revs[i-1]['size'])

        ANON = "ANONIPEDITS"
        authors = dict() # author:bytes
        for r in revs:
            if 'minor' in r:  
                pass # include minor edits
            user = r.get('user', u'')
            if 'anon' in r and (not user or self.ip_rex.match(user)): # anon
                authors[ANON] = authors.get(ANON, 0) + 1
            elif not user:
                continue
            elif self.bot_rex.search(user) or self.bot_rex.search(r.get('comment', '')):
                continue # filter bots
            else:
                if USE_DIFF_SIZE:
                    authors[user] = authors.get(user, 0) + abs(r['diff_size'])
                else:
                    authors[user] = authors.get(user, 0) + 1

        num_anon = authors.get(ANON, 0)
        try:
            del authors[ANON]
        except KeyError:
            pass

        if USE_DIFF_SIZE: # by summarized edit diff sizes
            authors = authors.items()
            authors.sort(lambda a,b:cmp(b[1], a[1]))
        else: # sorted by A-Z
            authors = authors.items()
            authors.sort()

        # append anon
        authors.append((("%s:%d"  % (ANON,num_anon),num_anon)))  #  append at the end
    #        print authors
        return [a for a,c in authors]

get_authors = inspect_authors().get_authors
