from mwlib.namespace_langs import lang_ns_data as _lang_ns_data

NS_MEDIA          = -2
NS_SPECIAL        = -1
NS_MAIN           =  0
NS_TALK           =  1
NS_USER           =  2
NS_USER_TALK      =  3
NS_PROJECT        =  4
NS_PROJECT_TALK   =  5
NS_IMAGE          =  6
NS_IMAGE_TALK     =  7
NS_MEDIAWIKI      =  8
NS_MEDIAWIKI_TALK =  9
NS_TEMPLATE       = 10
NS_TEMPLATE_TALK  = 11
NS_HELP           = 12
NS_HELP_TALK      = 13
NS_CATEGORY       = 14
NS_CATEGORY_TALK  = 15

namespace_maps = {}

def add_namespace_map(key, lang, project_name, extras={}):
    ns_data = _lang_ns_data[lang]
    res = dict(zip(ns_data, _lang_ns_data_keys))
    res[project_name] = NS_PROJECT
    res[ns_data[-1] % project_name] = NS_PROJECT_TALK
    res.update(extras)
    namespace_maps[key] = res

_lang_ns_data_keys = [
    NS_TALK, NS_USER, NS_USER_TALK, NS_IMAGE, NS_IMAGE_TALK,
    NS_MEDIAWIKI, NS_MEDIAWIKI_TALK, NS_TEMPLATE, NS_TEMPLATE_TALK,
    NS_HELP, NS_HELP_TALK, NS_CATEGORY, NS_CATEGORY_TALK, NS_SPECIAL, NS_MEDIA
]

add_namespace_map('enwiki', 'en', 'Wikipedia',
        {'Portal': 100, 'Portal_Talk': 101})
add_namespace_map('dewiki', 'de', 'Wikipedia',
        {'Portal': 100, 'Portal_Diskussion': 101})
for lang in _lang_ns_data:
    add_namespace_map('%s+en_mw' % lang, lang, 'MediaWiki', namespace_maps['enwiki'])

namespace_maps['default'] = dict(namespace_maps['enwiki'].items() + namespace_maps['dewiki'].items())

# external wikis:

dummy_interwikimap = {
    'wikipedia': 'wikipedia',
    'w': 'wikipedia',
    'wiktionary': 'wiktionary',
    'wikt': 'wiktionary',
    'wikinews': 'wikinews',
    'n': 'wikinews',
    'wikibooks': 'wikibooks',
    'b': 'wikibooks',
    'wikiquote': 'wikiquote',
    'q': 'wikiquote',
    'wikisource': 'wikisource',
    's': 'wikisource',
    'wikispecies': 'wikispecies',
    'species': 'wikispecies',
    'v': 'wikiversity',
    'wikimedia': 'wikimedia',
    'foundation': 'wikimedia',
    'commons': 'commons',
    'meta': 'meta',
    'm': 'meta',
    'incubator': 'incubator',
    'mw': 'mw',
    'mediazilla': 'mediazilla',
    
    'wikitravel': 'wikitravel',
}
