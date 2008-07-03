from mwlib import parser, log, metabook

log = log.Log('mwlib.writerbase')

class WriterError(RuntimeError):
    pass

def build_book(env, status_callback=None, progress_range=None):
    book = parser.Book()
    if status_callback is not None:
        progress = progress_range[0]
        num_articles = float(len(metabook.get_item_list(env.metabook,
            filter_type='article',
        )))
        if num_articles > 0:
            progress_step = int(
                (progress_range[1] - progress_range[0])/num_articles
            )
    for item in metabook.get_item_list(env.metabook):
        if item['type'] == 'chapter':
            book.children.append(parser.Chapter(item['title'].strip()))
        elif item['type'] == 'article':
            if status_callback is not None:
                status_callback(
                    status='parsing',
                    progress=progress,
                    article=item['title'],
                )
                progress += progress_step
            a = env.wiki.getParsedArticle(
                title=item['title'],
                revision=item.get('revision'),
            )
            if a is not None:
                if "displaytitle" in item:
                    a.caption = item['displaytitle']
                book.children.append(a)
            else:
                log.warn('No such article: %r' % item['title'])
    if status_callback is not None:
        status_callback(status='parsing', progress=progress, article='')
    return book
