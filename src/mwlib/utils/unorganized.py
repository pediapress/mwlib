import itertools
import logging
import os
import pprint
import re
import smtplib
import socket
import sys
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from typing import Union

import pypdf

log = logging.getLogger(__name__)

non_word = re.compile(r"(?u)[^-\w.~]")


def fs_escape(input_string: bytes | str) -> str:
    """Escape string to be safely used in path names."""
    if isinstance(input_string, bytes):
        input_string = input_string.decode("utf-8")
    if not input_string.isascii() or any(x in input_string for x in "~/\\"):
        result = []
        for char in input_string:
            if char.isascii() and char not in "~/\\":
                result.append(char)
            elif char == "~":
                result.append("~~")
            else:
                result.append(f"~{ord(char)}~")
        input_string = "".join(result)
    input_string = input_string.strip().replace(" ", "_")
    input_string = non_word.sub("", input_string)
    return input_string


def start_logging(path, stderr_only=False):
    """Redirect all output to sys.stdout or sys.stderr to be appended to a file,
    redirect sys.stdin to /dev/null.

    @param path: filename of logfile
    @type path: str

    @param stderr_only: if True, only redirect stderr, not stdout & stdin
    @type stderr_only: bool
    """

    if not stderr_only:
        sys.stdout.flush()
    sys.stderr.flush()

    log_file = open(path, "a", encoding="utf-8")  # noqa: SIM115
    file_no = log_file.fileno()

    if not stderr_only:
        os.dup2(file_no, 1)
    os.dup2(file_no, 2)

    if not stderr_only:
        null = os.open(os.path.devnull, os.O_RDWR)
        os.dup2(null, 0)
        os.close(null)


def get_multipart(filename, data, name):
    """Build data in format multipart/form-data to be used to POST binary data

    @param filename: filename to be used in multipart request
    @type filenaem: str

    @param data: binary data to include
    @type data: str

    @param name: name to be used in multipart request
    @type name: str

    @returns: tuple containing content-type and body for the request
    @rtype: (str, str)
    """

    if isinstance(filename, str):
        filename = filename.encode("utf-8", "ignore")
    if isinstance(name, str):
        name = name.encode("utf-8", "ignore")

    boundary = "-" * 20 + ("%f" % time.time()) + "-" * 20

    items = []
    items.append("--" + boundary)
    items.append(
        f'Content-Disposition: form-data; name="{name}"; filename="{filename}"'
    )
    items.append("Content-Type: application/octet-stream")
    items.append("")
    items.append(data)
    items.append("--" + boundary + "--")
    items.append("")

    body = "\r\n".join(items)
    content_type = f"multipart/form-data; boundary={boundary}"

    return content_type, body


def safe_unlink(filename):
    """Never failing os.unlink()"""

    try:
        os.unlink(filename)
    except Exception as exc:
        log.warning(f"Could not remove file {filename!r}: {exc}")


fetch_cache = {}


def check_content_type(expected_content_type, result, ignore_errors=False):
    if not expected_content_type:
        return
    content_type = result.headers.get_content_type()
    if content_type != expected_content_type:
        msg = f"Got content-type {content_type!r}, expected {expected_content_type!r}"
        if ignore_errors:
            log.warning(msg)
        else:
            raise RuntimeError(msg)


def fetch_url(
    url,
    ignore_errors=False,
    fetch_cache=fetch_cache,
    max_cacheable_size=1024,
    expected_content_type=None,
    opener=None,
    output_filename=None,
    post_data=None,
    timeout=10.0,
):
    """Fetch given URL via HTTP

    @param ignore_errors: if True, log but otherwise ignore errors, return None
    @type ignore_errors: bool

    @param fetch_cache: dictionary used as cache, with urls as keys and fetched
        data as values
    @type fetch_cache: dict

    @param max_cacheable_size: max. size for responses to be cached
    @type max_cacheable_size: int

    @param expected_content_type: if given, raise (or log) an error if the
        content-type of the reponse does not mathc
    @type expected_content_type: str

    @param opener: if give, use this opener instead of instantiating a new one
    @type opener: L{urllib2.URLOpenerDirector}

    @param output_filename: write response to given file
    @type output_filename: str

    @param post_data: if given use POST request
    @type post_data: dict

    @param timeout: timeout in seconds
    @type timeout: float

    @returns: fetched response or True if filename was given; None when
        ignore_errors is True, and the request failed
    @rtype: str
    """

    if not post_data and url in fetch_cache:
        return fetch_cache[url]
    log.info(f"fetching {url!r}")
    if not hasattr(socket, "_delegate_methods"):  # not using gevent?
        socket.setdefaulttimeout(timeout)
    if opener is None:
        opener = urllib.request.build_opener()
        opener.addheaders = [("User-agent", "mwlib")]
    try:
        if post_data:
            post_data = urllib.parse.urlencode(post_data)
        result = opener.open(url, post_data)
        data = result.read()
        check_content_type(expected_content_type, result, ignore_errors)

    except urllib.error.URLError as err:
        if ignore_errors:
            log.error(f"{err} - while fetching {url!r}")
            return None
        raise RuntimeError(f"Could not fetch {url!r}: {err}") from err

    if hasattr(fetch_cache, "max_cacheable_size"):
        max_cacheable_size = max(fetch_cache.max_cacheable_size, max_cacheable_size)
    if len(data) <= max_cacheable_size:
        fetch_cache[url] = data

    if output_filename:
        with open(output_filename, "wb") as out_file:
            out_file.write(data)
        return True
    return data


def uid(max_length=10):
    """Generate a unique identifier of given maximum length

    @parma max_length: maximum length of identifier
    @type max_length: int

    @returns: unique identifier
    @rtype: str
    """

    some_bytes = os.urandom((max_length + 1) // 2)
    return "".join(hex(x)[2:] for x in some_bytes)[:max_length]


def ensure_dir(directory_path):
    """If directory directory_path does not exist, create it

    @param directory_path: name of an existing or not-yet-existing directory
    @type directory_path: str

    @returns: directory_path
    @rtype: str
    """

    if not os.path.isdir(directory_path):
        os.makedirs(directory_path)
    return directory_path


def send_mail(from_email, to_emails, subject, body, headers=None, host="mail", port=25):
    """Send an email via SMTP

    @param from_email: email address for From: header
    @type from_email: str

    @param to_emails: sequence of email addresses for To: header
    @type to_email: [str]

    @param subject: text for Subject: header
    @type subject: unicode

    @param body: text for message body
    @type body: unicode

    @param host: mail server host
    @type host: str

    @param port: mail server port
    @type port: int
    """

    connection = smtplib.SMTP(host, port)
    msg = MIMEText(body.encode("utf-8"), "plain", "utf-8")
    msg["Subject"] = subject.encode("utf-8")
    msg["From"] = from_email
    msg["To"] = ", ".join(to_emails)
    msg["Date"] = formatdate()
    msg["Message-ID"] = make_msgid()
    if headers is not None:
        for k, header in headers.items():
            if not isinstance(header, str):
                header = str(header)
            msg[k] = header
    connection.sendmail(from_email, to_emails, msg.as_string())
    connection.close()


def ppdict(dct):
    items = sorted(dct.items())
    tmp = []
    write = tmp.append

    for k, val in items:
        write("*" + str(k) + "*")
        val = str(val)
        lines = val.split("\n")
        for line in lines:
            write(" " * 4 + line)
        write("")

    return "\n".join(tmp)


def report(
    system="",
    subject="",
    from_email=None,
    mail_recipients=None,
    mail_headers=None,
    **kw,
):
    log.info(f"system={system!r} subject={subject!r}")

    text = []
    text.append("SYSTEM: %r\n" % system)
    text.append(f"{traceback.format_exc()}\n")
    try:
        fqdn = socket.getfqdn()
    except OSError:
        fqdn = "not available"

    text.append("CWD: %r\n" % os.getcwd())

    text.append(ppdict(kw))
    # text.append('KEYWORDS:\n%s\n' % pprint.pformat(kw, indent=4))
    text.append("ENV:\n%s\n" % pprint.pformat(dict(os.environ), indent=4))

    text = "\n".join(text)

    if not (from_email and mail_recipients):
        return text

    try:
        if not isinstance(subject, str):
            subject = repr(subject)
        send_mail(
            from_email,
            mail_recipients,
            f"REPORT [{fqdn}]: {subject}",
            text,
            headers=mail_headers,
        )
        log.info("sent mail to %r" % mail_recipients)
    except Exception as exc:
        log.ERROR("Could not send mail: %s" % exc)
    return text


def get_safe_url(url):
    if not isinstance(url, str):
        url = url.encode("utf-8")

    nonwhitespace_rex = re.compile(r"^\S+$")
    try:
        result = urllib.parse.urlsplit(url)
        scheme, netloc, path, query, fragment = result
    except Exception as exc:
        log.warning(f"urlparse({url!r}) failed: {exc}")
        return None

    if not (scheme and netloc):
        log.warning(f"Empty scheme or netloc: {scheme!r} {netloc!r}")
        return None

    if not (nonwhitespace_rex.match(scheme) and nonwhitespace_rex.match(netloc)):
        log.warning(f"Found whitespace in scheme or netloc: {scheme!r} {netloc!r}")
        return None

    try:
        # catches things like path='bla " target="_blank'
        path = urllib.parse.quote(urllib.parse.unquote(path))
    except Exception as exc:
        log.warning(f"quote(unquote({path!r})) failed: {exc}")
        return None
    try:
        return urllib.parse.urlunsplit(
            (scheme, netloc, path, query, fragment)
        )
    except Exception as exc:
        log.warning(f"urlunparse() failed: {exc}")
    return None


def get_nodeweight(obj):
    """
    utility function that returns a
    node class and it's weight
    can be used for statistics
    to get some stats when NO Advanced Nodes are available
    """
    k = obj.__class__.__name__
    if k in ("Text",):
        return k, len(obj.caption)
    if k == "ImageLink" and obj.is_inline():
        return "InlineImageLink", 1
    return k, 1


# -- extract text from pdf file. used for testing only.
def pdf2txt(path):
    """extract text from pdf file"""
    # based on http://code.activestate.com/recipes/511465/
    content = []
    reader = pypdf.PdfReader(path)

    num_pages = len(reader.pages)
    for i in range(0, num_pages):
        # Extract text from page and add to content
        content.append(reader.pages[i].extract_text())

    return "\n".join(content)


def garble_password(argv):
    argv = list(argv)
    idx = 0
    while True:
        try:
            idx = argv[idx:].index("--password") + 1
        except ValueError:
            break
        if idx >= len(argv):
            break
        argv[idx] = "{OMITTED}"
    return argv


def python2sort(iterable, reverse=False):
    if not iterable:
        return iterable
    iterator = iter(iterable)
    groups = [[next(iterator)]]
    for item in iterator:
        for group in groups:
            try:
                item < group[0]  # exception if not comparable
                group.append(item)
                break
            except TypeError:
                continue
        else:  # did not break, make new group
            groups.append([item])
    log.debug(groups)  # for debugging
    result = itertools.chain.from_iterable(sorted(group) for group in groups)
    if reverse:
        result = reversed(list(result))
    return result


def split_tag(txt, flags=re.DOTALL):
    matched_tag = re.match(r" *(\w+)(.*)", txt, flags)
    if matched_tag is None:
        raise ValueError("could not match tag name")
    name = matched_tag.group(1)
    values = matched_tag.group(2)
    return name, values
