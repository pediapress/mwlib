#! /usr/bin/env python3

# Copyright (c) 2007-2023, PediaPress GmbH
# See README.rst for additional licensing information.

import csv
import os
import sys
import tempfile

from mwlib.utils.mwlib_exceptions import ImageDbError

try:
    import simplejson as json
except ImportError:
    import json


class License:
    def __init__(self, name="", display_name="",
                 license_type=None, description=""):
        self.name = name
        self.display_name = display_name
        self.license_type = license_type  # free|nonfree|unrelated|unknown
        self.description = description

    def __str__(self):
        display_name = f" - text: {self.display_name}" if self.display_name else ""
        return f"<License:{self.name!r} - type:{self.license_type!r}{display_name!r}>"

    __repr__ = __str__

    def __cmp__(self, other):
        if self.display_name < other.display_name:
            return -1
        elif self.display_name == other.display_name:
            return 0
        else:
            return 1


class LicenseChecker:
    def __init__(self, image_db=None, filter_type=None):
        self.image_db = image_db
        self.filter_type = self._check_filter_type(filter_type, default_filter="blacklist")
        self.licenses = {}
        self.display_cache = {}

        # stats related attributes
        self.unknown_licenses = {}
        self.rejected_images = set()
        self.accepted_images = set()
        self.license_display_name = {}

    def read_licenses_csv(self, file_name=None):
        if not file_name:
            file_name = os.path.join(os.path.dirname(__file__), "wplicenses.csv")
        with open(file_name) as csv_file:
            for data in csv.reader(csv_file):
                try:
                    (name, display_name, license_type,
                     _, license_description) = data
                except ValueError:
                    continue
                if not name:
                    continue
                name = name.lower()
                lic = License(name=name)
                lic.display_name = display_name
                if license_description.startswith("-"):
                    license_description = license_description[1:]
                lic.description = license_description.strip()
                if license_type in ["free-display", "nonfree-display"]:
                    lic.license_type = "free"
                elif license_type in ["nonfree"]:
                    lic.license_type = "nonfree"
                else:
                    lic.license_type = "unrelated"
                self.licenses[name] = lic

    @staticmethod
    def _check_filter_type(filter_type=None, default_filter="blacklist"):
        if filter_type in ["blacklist", "whitelist", "nofilter"]:
            return filter_type
        else:
            return default_filter

    def _get_licenses(self, templates):
        licenses = []
        for template in templates:
            if not isinstance(template, str):
                raise TypeError("template must be a string")
            lic = self.licenses.get(template, None)
            if not lic:
                lic = License(name=template)
                lic.license_type = "unknown"
            licenses.append(lic)
        return licenses

    def _check_licenses(self, licenses, imgname, stats=True):
        if not self.image_db:
            raise ImageDbError(
                "No image_db passed when initializing LicenseChecker")
        for lic in licenses:
            if lic.license_type == "free":
                self.license_display_name[imgname] = lic.display_name
                return True
            elif lic.license_type == "nonfree":
                self.license_display_name[imgname] = lic.display_name
                return self.filter_type == "nofilter"
        for lic in licenses:
            if lic.license_type == "unknown" and stats:
                urls = self.unknown_licenses.get(lic.name, set())
                urls.add(
                    self.image_db.get_description_url(imgname)
                    or self.image_db.get_url(imgname)
                    or imgname
                )
                self.unknown_licenses[lic.name] = urls
        self.license_display_name[imgname] = ""
        if self.filter_type == "whitelist":
            return False
        elif self.filter_type in ["blacklist", "nofilter"]:
            return True

    def display_image(self, imgname):
        if imgname in self.display_cache:
            return self.display_cache[imgname]
        if self.image_db is None:
            return False
        templates = [t.lower() for t in self.image_db.get_image_templates_and_args(
            imgname)]
        licenses = self._get_licenses(templates)
        display_img = self._check_licenses(licenses, imgname)
        url = self.image_db.get_description_url(imgname) or self.image_db.get_url(
            imgname) or imgname
        if display_img:
            self.accepted_images.add(url)
        else:
            self.rejected_images.add(url)
        self.display_cache[imgname] = display_img
        return display_img

    def get_license_display_name(self, imgname):
        text = self.license_display_name.get(imgname, None)
        if text is not None:
            return text
        else:
            self.display_image(imgname)
            return self.license_display_name.get(imgname, "")

    @property
    def free_img_ratio(self):
        num_rejected_images = len(self.rejected_images)
        num_accepted_images = len(self.accepted_images)
        ratio = num_accepted_images / (num_accepted_images + num_rejected_images) if num_accepted_images + num_rejected_images > 0 else 1
        return ratio

    def dump_stats(self):
        stats = [
            "IMAGE LICENSE STATS - accepted: %d - rejected: %d --> accept ratio: %.2f"
            % (len(self.accepted_images), len(self.rejected_images),
               self.free_img_ratio)
        ]

        images = set()
        for urls in self.unknown_licenses.values():
            for url in urls:
                images.add(repr(url))
        stats.append("Images without license information: %s" % (" ".join(
            list(images))))
        stats.append("##############################")
        stats.append("Rejected Images: %s" % " ".join(
            list(self.rejected_images)))
        return "\n".join(stats)

    def dump_unknown_licenses(self, _dir):
        if not self.unknown_licenses:
            return
        unknown_licenses = {}
        for lic, urls in self.unknown_licenses.items():
            unknown_licenses[lic] = list(urls)
        with tempfile.NamedTemporaryFile(
            dir=_dir, prefix="licensestats_", suffix=".json", mode="w"
        ) as temp_file:
            json.dump(unknown_licenses, temp_file)

    def analyse_unknown_licenses(self, _dir):
        files = os.listdir(_dir)
        unknown_licenses = {}
        for file_name in files:
            file_name = os.path.join(_dir, file_name)
            if not file_name.endswith("json"):
                continue
            with open(file_name, encoding="utf-8") as file:
                content = str(file.read())
            try:
                licenses = json.loads(content)
            except ValueError:
                print("no json object found in file", file_name)
                continue
            for lic, urls in licenses.items():
                if not self.licenses.get(lic, False):
                    seen_urls = unknown_licenses.get(lic, set())
                    seen_urls.update(set(urls))
                    unknown_licenses[lic] = seen_urls
        sorted_licenses = [
            (len(urls), lic, urls) for lic, urls in unknown_licenses.items()
        ]
        sorted_licenses.sort(reverse=True)
        for num_urls, lic, urls in sorted_licenses:
            img_str = "\n".join(list(list(urls)[:5])),
            print(f"\nTEMPLATE: {lic} (num rejected images: {num_urls})\nIMAGES:\n{img_str}\n")

    def dump_license_info_content(self):
        licenses = sorted(self.licenses.values())

        tmpl_txt = """
{{/ImageLicenseItem
|template_name=%(lic_name)s
|license=%(display_name)s
|display_allowed=%(allowed)s
|license_text_url=
|full_text_required=
|description=%(description)s
}}"""

        for lic in licenses:
            if lic.license_type in ["free", "nonfree"]:
                allowedstr = "yes" if lic.license_type == "free" else "no"

                print(
                    tmpl_txt
                    % {
                        "lic_name": lic.name,
                        "display_name": lic.display_name,
                        "allowed": allowedstr,
                        "description": lic.description,
                    }
                )


if __name__ == "__main__":
    lc = LicenseChecker()
    lc.read_licenses_csv()

    STATS_DIR = sys.argv[1] if len(sys.argv) > 1 else os.environ.get(
        "HIQ_STATSDIR")
    if not STATS_DIR:
        print(
            "specify stats_dir as first arg, or set environment var HIQ_STATSIDR")
        sys.exit(1)

    lc.analyse_unknown_licenses(STATS_DIR)
