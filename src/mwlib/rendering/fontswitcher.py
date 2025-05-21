#!/usr/bin/env python

import re
from pathlib import Path


class Scripts:
    def __init__(self):
        scripts_filename = Path(__file__).parent / "scripts.txt"
        self.script2code_block = {}
        self.code_block2scripts = []
        self.read_script_file(scripts_filename)

    def read_script_file(self, file_name):
        if not file_name.exists():
            raise OSError(f"scripts.txt file not found at: {file_name!r}")
        with file_name.open() as script_file:
            for line in script_file.readlines():
                res = re.search("([A-Z0-9]+)\\.\\.([A-Z0-9]+); (.*)",
                                line.strip())
                if res:
                    start_block, end_block, the_script = res.groups()
                    self.script2code_block[the_script.lower()] = (
                        int(start_block, 16),
                        int(end_block, 16),
                    )
                    self.code_block2scripts.append(
                        (int(start_block, 16), int(end_block, 16), the_script)
                    )

    def get_code_points(self, the_script):
        code_block = self.script2code_block.get(the_script.lower())
        if not code_block:
            return 0, 0
        else:
            return code_block

    def get_scripts_for_code_block(self, code_block):
        the_scripts = set()
        for start_block, end_block, the_script in self.code_block2scripts:
            if start_block <= code_block[0] <= end_block:
                the_scripts.add(the_script)
            if start_block <= code_block[1] <= end_block:
                the_scripts.add(the_script)
                break
        return the_scripts

    def get_scripts_for_code_blocks(self, code_blocks):
        the_scripts = set()
        for code_block in code_blocks:
            the_scripts = the_scripts.union(
                self.get_scripts_for_code_block(code_block))
        return the_scripts

    def get_scripts(self, txt):
        the_scripts = set()
        idx = 0
        txt_len = len(txt)
        while idx < txt_len:
            for block_start, block_end, the_script in self.code_block2scripts:
                while idx < txt_len and block_start <= ord(txt[idx]) <= block_end:
                    if txt[idx] != " ":
                        the_scripts.add(the_script)
                    idx += 1
        return list(the_scripts)


class FontSwitcher:
    def __init__(self, char_blacklist_file=None):
        self.scripts = Scripts()
        self.default_font = None
        self.code_points2font = []

        self.space_like_chars = [i for i in range(33) if i not in [9, 10, 13]] + [127]
        self.remove_chars = [173]  # 173 is a soft hyphen
        self.ignore_chars = [
            8206,  # left to right mark
            8207,  # right to left mark
        ]
        self.no_switch_chars = self.space_like_chars + self.ignore_chars + self.remove_chars
        self.char_blacklist = self.read_char_blacklist(char_blacklist_file)

        self.cjk_fonts = []  # list of font names for cjk scripts
        self.space_cjk = False  # when switching fonts, indicate that cjk text is present

    @staticmethod
    def read_char_blacklist(char_blacklist_file):
        if not char_blacklist_file:
            return {}
        char_blacklist = {}
        with open(char_blacklist_file) as blacklist_file:
            for char in blacklist_file.readlines():
                if char:
                    char = int(char.strip())
                    char_blacklist[char] = True
        return char_blacklist

    def unregister_font(self, font_name_to_unregister):
        registered_entries = []
        i = 0
        for i, (_, _, font_name) in enumerate(self.code_points2font):
            if font_name_to_unregister == font_name:
                registered_entries.append(i)
        registered_entries.reverse()
        for entry in registered_entries:
            self.code_points2font.pop(entry)

    def register_font(self, font_name, code_points: list):
        """Register a font to certain scripts
        or a range of code point blocks"""
        if not code_points:
            return
        for block in code_points:
            if isinstance(block, str):
                block = self.scripts.get_code_points(block)
            block_start, block_end = block
            self.code_points2font.insert(0, (block_start,
                                             block_end, font_name))

    def register_default_font(self, font_name=None):
        self.default_font = font_name

    def get_font(self, ord_char):
        for block_start, block_end, font_name in self.code_points2font:
            if block_start <= ord_char <= block_end:
                return font_name
        return self.default_font

    def _append_text_and_font_to_list(self, font, txt, new_txt_list):
        if font != self.default_font:
            if txt.startswith(" "):
                new_txt_list.append((" ", self.default_font))
                new_txt_list.append((txt[1:], font))
            elif txt.endswith(" "):
                new_txt_list.append((txt[:-1], font))
                new_txt_list.append((" ", self.default_font))
            else:
                new_txt_list.append((txt, font))
        else:
            new_txt_list.append((txt, font))

    def get_font_list(self, txt, spaces_to_default=False):
        last_font, last_txt, txt_list = self.extract_last_font_last_text_and_text_list(txt)

        if last_txt:
            txt_list.append(("".join(last_txt), last_font))

        if spaces_to_default:
            new_txt_list = []
            for txt, font in txt_list:
                self._append_text_and_font_to_list(font, txt, new_txt_list)
            txt_list = new_txt_list

        if self.space_cjk:
            for txt, font in txt_list:
                if font in self.cjk_fonts:
                    return txt_list, True
            return txt_list, False
        return txt_list

    def _get_processed_char_and_font(self, ord_c, blacklisted, last_font, text_char):
        if ord_c in self.remove_chars:
            text_char = ""
        if ord_c in self.space_like_chars:
            text_char = " "
        if blacklisted:
            text_char = chr(9633)  # U+25A1 WHITE SQUARE
        font = last_font if last_font else self.default_font
        return text_char, font

    def extract_last_font_last_text_and_text_list(self, txt: str | bytes):
        txt_list = []
        last_font = None
        last_txt = []
        if isinstance(txt, bytes):
            txt = txt.decode("utf-8")
        for text_char in txt:
            try:
                ord_c = ord(text_char)
            except TypeError:
                raise TypeError(f"Invalid character in text: {text_char!r}")
            blacklisted = self.char_blacklist.get(ord_c, False)
            if ord_c in self.no_switch_chars or blacklisted:
                text_char, font = self._get_processed_char_and_font(ord_c, blacklisted, last_font, text_char)
            else:
                font = self.get_font(ord_c)
            if font != last_font and last_txt:
                txt_list.append(("".join(last_txt), last_font))
                last_txt = []
            last_txt.append(text_char)
            last_font = font
        return last_font, last_txt, txt_list


if __name__ == "__main__":
    _scripts = Scripts()

    blocks = [
        (9472, 9580),
    ]

    scripts = _scripts.get_scripts_for_code_blocks(blocks)
    print(scripts)
    for script in scripts:
        print(_scripts.get_code_points(script))
