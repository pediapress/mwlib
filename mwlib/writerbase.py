from mwlib import parser, log

log = log.Log('mwlib.writerbase')

class WriterError(RuntimeError):
    pass

def build_book(env, status_callback=None, progress_range=None):
    book = parser.Book()
    if status_callback is not None:
        progress = progress_range[0]
        num_articles = float(len(list(env.metabook.getArticles())))
        if num_articles > 0:
            progress_step = int((progress_range[1] - progress_range[0])/num_articles)
    for item in env.metabook.getItems():
        if item['type'] == 'chapter':
            book.children.append(parser.Chapter(item['title'].strip()))
        elif item['type'] == 'article':
            if status_callback is not None:
                status_callback(status='parsing', progress=progress, article=item['title'])
                progress += progress_step
            a = env.wiki.getParsedArticle(title=item['title'], revision=item.get('revision'))
            if a is not None:
                book.children.append(a)
            else:
                log.warn('No such article: %r' % item['title'])
    if status_callback is not None:
        status_callback(status='parsing', progress=progress, article='')
    return book
