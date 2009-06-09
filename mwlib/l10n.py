from itertools import dropwhile
import os
import subprocess

ext2lang = {
    '.py': 'Python',
}

def execute(*args):
    popen = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output = popen.stdout.read()
    errors = popen.stdout.read()
    popen.wait()
    if errors:
        raise RuntimeError('Errors while executing %r: %s' % (
            ' '.join(args),
            errors),
        )
    elif popen.returncode != 0:
        raise RuntimeError('Got returncode %d != 0 when executing %r' % (
            popen.returncode, ' '.join(args),
        ))
    return output

def make_messages(locale, domain, version, inputdir,
    localedir='locale',
    extensions=('.py',),
):
    assert os.path.isdir(localedir), 'no directory %s found' % (localedir,)
    assert os.path.isdir(inputdir), 'no directory %s found' % (inputdir,)
    
    languages = []
    if locale == 'all':
        languages = [lang for lang in os.listdir(localedir) if not lang.startswith('.')]
    else:
        languages.append(locale)
    
    for locale in languages:
        print "processing language", locale
        basedir = os.path.join(localedir, locale, 'LC_MESSAGES')
        if not os.path.isdir(basedir):
            os.makedirs(basedir)
        
        pofile = os.path.join(basedir, '%s.po' % domain)
        potfile = os.path.join(basedir, '%s.pot' % domain)
        
        if os.path.exists(potfile):
            os.unlink(potfile)
        
        all_files = []
        for (dirpath, dirnames, filenames) in os.walk(inputdir):
            all_files.extend([(dirpath, f) for f in filenames])
        all_files.sort()
        for dirpath, filename in all_files:
            file_base, file_ext = os.path.splitext(filename)
            if file_ext not in extensions:
                continue
            msgs = execute(
                'xgettext',
                '--default-domain', domain,
                '--language', ext2lang[file_ext],
                '--from-code', 'UTF-8',
                '--output', '-',
                os.path.join(dirpath, filename),
            )
            if os.path.exists(potfile):
                # Strip the header
                msgs = '\n'.join(dropwhile(len, msgs.split('\n')))
            else:
                msgs = msgs.replace('charset=CHARSET', 'charset=UTF-8')
            if msgs:
                open(potfile, 'ab').write(msgs)
        
        if os.path.exists(potfile):
            msgs = execute('msguniq', '--to-code', 'UTF-8', potfile)
            open(potfile, 'wb').write(msgs)
            if os.path.exists(pofile):
                msgs = execute('msgmerge', '--quiet', pofile, potfile)
            open(pofile, 'wb').write(msgs)
            os.unlink(potfile)


def compile_messages(localedir='locale'):
    for dirpath, dirnames, filenames in os.walk(localedir):
        for f in filenames:
            if f.endswith('.po'):
                path = os.path.join(dirpath, f)
                mo_filename = os.path.splitext(path)[0] + '.mo'
                try:
                    execute('msgfmt', '--check-format', '--output-file', mo_filename, path)
                except RuntimeError, exc:
                    print 'Could not compile %r: %s' % (path, exc)
