# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.

all: commands.html configfiles.html writers.html zipfile.html metabook.html

%.html: %.txt
	rst2html.py $< >$@
