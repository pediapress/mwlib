# Copyright (c) 2007-2008 PediaPress GmbH
# See README.txt for additional licensing information.

RST2HTML ?= rst2html.py

all: commands.html configfiles.html writers.html metabook.html

%.html: %.txt
	$(RST2HTML) $< >$@
