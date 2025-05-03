import os
import subprocess
from itertools import dropwhile

ext2lang = {
    ".py": "Python",
}


def execute(*args):
    popen = subprocess.Popen(args, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
    output, errors = popen.communicate()
    popen.wait()
    if errors:
        raise RuntimeError(
            f"Errors while executing {' '.join(args)!r}: {errors}",
        )
    elif popen.returncode != 0:
        raise RuntimeError(
            f"Got returncode {popen.returncode} != 0 when executing {' '.join(args)!r}"
        )
    return output


def _process_and_merge_localization_files(pot_file_path, po_file_path):
    if os.path.exists(pot_file_path):
        msgs = execute("msguniq", "--to-code", "UTF-8", pot_file_path)
        with open(pot_file_path, "wb") as pot_file:
            pot_file.write(msgs)
        if os.path.exists(po_file_path):
            msgs = execute("msgmerge", "--quiet", po_file_path, pot_file_path)
        with open(po_file_path, "wb") as po_file:
            po_file.write(msgs)
        os.unlink(pot_file_path)


def _generate_message_catalog_from_file(dirpath, filename, extensions, domain, pot_file_path):
    _, file_ext = os.path.splitext(filename)
    if file_ext not in extensions:
        return
    msgs = execute(
        "xgettext",
        "--default-domain",
        domain,
        "--language",
        ext2lang[file_ext],
        "--from-code",
        "UTF-8",
        "--output",
        "-",
        os.path.join(dirpath, filename),
    )
    if os.path.exists(pot_file_path):
        # Strip the header
        msgs = "\n".join(dropwhile(len, msgs.split("\n")))
    else:
        msgs = msgs.replace("charset=CHARSET", "charset=UTF-8")
    if msgs:
        with open(pot_file_path, "ab") as pot_file:
            pot_file.write(msgs)


def make_messages(
    locale,
    domain,
    _,
    inputdir,
    localedir="locale",
    extensions=(".py",),
):
    if not os.path.isdir(localedir):
        raise ValueError(f"no directory {localedir!r} found")
    if not os.path.isdir(inputdir):
        raise ValueError(f"no directory {inputdir!r} found")

    languages = []
    if locale == "all":
        languages = [lang for lang in os.listdir(localedir) if not lang.startswith(".")]
    else:
        languages.append(locale)

    for locale in languages:
        print("processing language", locale)
        basedir = os.path.join(localedir, locale, "LC_MESSAGES")
        if not os.path.isdir(basedir):
            os.makedirs(basedir)

        po_file_path = os.path.join(basedir, "%s.po" % domain)
        pot_file_path = os.path.join(basedir, "%s.pot" % domain)

        if os.path.exists(pot_file_path):
            os.unlink(pot_file_path)

        all_files = []
        for dirpath, _, filenames in os.walk(inputdir):
            all_files.extend([(dirpath, f) for f in filenames])
        all_files.sort()
        for dirpath, filename in all_files:
            _generate_message_catalog_from_file(
                dirpath,
                filename,
                extensions,
                domain,
                pot_file_path)

        _process_and_merge_localization_files(pot_file_path, po_file_path)


def compile_messages(localedir="locale"):
    for dirpath, _, filenames in os.walk(localedir):
        for filename in filenames:
            if filename.endswith(".po"):
                path = os.path.join(dirpath, filename)
                mo_filename = os.path.splitext(path)[0] + ".mo"
                try:
                    execute(
                        "msgfmt", "--check-format", "--output-file",
                        mo_filename, path
                    )
                except RuntimeError as exc:
                    print(f"Could not compile {path!r}: {exc}")
