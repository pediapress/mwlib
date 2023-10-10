#! /usr/bin/env python

# Copyright (c) 2007, PediaPress GmbH
# See README.txt for additional licensing information.

# the code below is based on the html formatter example on http://pygments.org/docs/formatterdevelopment/

from xml.sax.saxutils import escape as xmlescape

from pygments.formatter import Formatter


class ReportlabFormatter(Formatter):
    def __init__(self, font_size=10, font_name=None,
                 background_color=None, **options):
        Formatter.__init__(self, **options)
        self.font_name = font_name
        self.font_size = font_size
        background_color = background_color or "#ffffff"
        self.background_color = background_color
        # create a dict of (start, end) tuples that wrap the
        # value of a token so that we can use it in the format
        # method later
        self.styles = {}

        # we iterate over the `_styles` attribute of a style item
        # that contains the parsed style values.
        for token, style in self.style:
            start = end = ""
            # a style item is a tuple in the following form:
            # colors are readily specified in hex: 'RRGGBB'
            if style["color"]:
                start += '<font color="#%s">' % style["color"]
                end = "</font>" + end
            if style["bold"]:
                start += "<b>"
                end = "</b>" + end
            if style["italic"]:
                start += "<i>"
                end = "</i>" + end
            if style["underline"]:
                start += "<u>"
                end = "</u>" + end
            self.styles[token] = (start, end)

    def format(self, tokensource, outfile):
        # lastval is a string we use for caching
        # because it's possible that an lexer yields a number
        # of consecutive tokens with the same token type.
        # to minimize the size of the generated html markup we
        # try to join the values of same-type tokens here
        lastval = ""
        lasttype = None

        # wrap the whole output with <pre>
        output = f'<para backcolor="{self.background_color}"><font name="{self.font_name}" size="{self.font_size}">'
        outfile.write(output.encode(self.encoding))

        for ttype, value in tokensource:
            # if the token type doesn't exist in the stylemap
            # we try it with the parent of the token type
            # eg: parent of Token.Literal.String.Double is
            # Token.Literal.String
            while ttype not in self.styles:
                ttype = ttype.parent
            if ttype == lasttype:
                # the current token type is the same of the last
                # iteration. cache it
                lastval += value
            else:
                # not the same token as last iteration, but we
                # have some data in the buffer. wrap it with the
                # defined style and write it to the output file
                if lastval:
                    stylebegin, styleend = self.styles[lasttype]
                    output = stylebegin + xmlescape(lastval) + styleend
                    outfile.write(output.encode(self.encoding))
                # set lastval/lasttype to current values
                lastval = value
                lasttype = ttype

        # if something is left in the buffer, write it to the
        # output file, then close the opened <pre> tag
        if lastval:
            stylebegin, styleend = self.styles[lasttype]
            output = stylebegin + xmlescape(lastval) + styleend
            outfile.write(output.encode(self.encoding))
        outfile.write("</font></para>\n".encode(self.encoding))
