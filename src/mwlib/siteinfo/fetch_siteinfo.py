#!/usr/bin/env python3

import json
import sys
from urllib.error import URLError
from urllib.request import urlopen


def fetch(lang):
    url = (
        f"https://{lang}.wikipedia.org/w/api.php?action=query&meta=siteinfo&"
        f"siprop=general|namespaces|namespacealiases|magicwords|interwikimap&format=json"
    )

    print(f"fetching {url}")
    try:
        data = urlopen(url).read()
    except URLError as e:
        print(f"error fetching {url}: {e}")
        return
    site_info_path = f"siteinfo-{lang}.json"
    print(f"writing {site_info_path}")
    data = json.loads(data)["query"]
    with open(site_info_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, sort_keys=True)


def main(argv):
    languages = argv[1:]
    if not languages:
        languages = "de en es fr it ja nl no pl pt simple sv".split()

    for lang in languages:
        fetch(lang.lower())


if __name__ == "__main__":
    main(sys.argv)
