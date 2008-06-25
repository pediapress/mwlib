from mwlib import advtree, parser

class WriterError(RuntimeError):
    pass

def build_book(env):
    book = parser.Book()
    for item in env.metabook.getItems():
        if item['type'] == 'chapter':
            book.children.append(parser.Chapter(item['title'].strip()))
        elif item['type'] == 'article':
            a = env.wiki.getParsedArticle(title=item['title'], revision=item.get('revision'))
            advtree.buildAdvancedTree(a)
            book.children.append(a)
    return book
